"""Render a frozen locator rectangle to a new PNG. Producing pixels is not viewing them."""
from contextlib import ExitStack, closing, contextmanager
from hashlib import sha256
from io import BytesIO
import math
import ntpath
import os
from pathlib import Path, PureWindowsPath
import stat
from uuid import uuid4

from reading_pdf_elements import ElementError, MAX_SOURCE_BYTES, load
from reading_sections import _native

MIN_SCALE, MAX_SCALE = 0.25, 8.0
MAX_SIDE = 32_768          # includes the virtual page used by PDFium's coordinate transform
MAX_PIXELS = 16_000_000    # only the requested crop is allocated


def _relative(value):
    # Apply the same path policy on POSIX and Windows, including drive-relative
    # paths, NTFS alternate streams, device aliases, and trailing dot/space aliases.
    if not isinstance(value, (str, os.PathLike)):
        raise ElementError('INVALID_ARGUMENT', 'Use a run-relative file path.')
    path = PureWindowsPath(value)
    is_reserved = getattr(ntpath, 'isreserved', lambda p: PureWindowsPath(p).is_reserved())
    if (path.anchor or not path.parts or any(p == '..' or p.endswith(('.', ' ')) or is_reserved(p)
            or any(c in '<>:"|?*' or ord(c) < 32 for c in p) for p in path.parts)):
        raise ElementError('INVALID_ARGUMENT', 'Use an unambiguous run-relative path without traversal.')
    return Path(*path.parts)


def _check_path(path, *, missing_ok=False):
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing_ok:
            return False
        raise
    if (stat.S_ISLNK(info.st_mode) or
            getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise ElementError('INVALID_ARGUMENT', 'Symlinks and reparse points are not crop paths: '+str(path))
    return True


@contextmanager
def _output_parent(root, parent):
    """Keep mkdir and no-clobber publication beneath real directories, even during link swaps."""
    with ExitStack() as stack:
        if os.name == 'nt':
            # Windows lacks openat. Pin the directory itself (do not follow a
            # reparse point); share read, but not write/delete, until publication.
            import _winapi
            directory = root
            for part in (None, *parent.parts):
                if part is not None:
                    directory /= part
                    directory.mkdir(exist_ok=True)
                handle = _winapi.CreateFile(str(directory), 0, 1, 0, _winapi.OPEN_EXISTING,
                                            0x02000000 | 0x00200000, 0)  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
                stack.callback(_winapi.CloseHandle, handle)
                _check_path(directory)
            yield directory, None
        else:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            fd = os.open(root, flags)
            stack.callback(os.close, fd)
            for part in parent.parts:
                try:
                    os.mkdir(part, dir_fd=fd)
                except FileExistsError:
                    pass
                fd = os.open(part, flags, dir_fd=fd)
                stack.callback(os.close, fd)
            yield Path('.'), fd


def _publish(root, out, png):
    with _output_parent(root, out.parent) as (directory, fd):
        temporary = directory / ('.crop-'+uuid4().hex+'.png')
        dest = directory / out.name
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_BINARY', 0)
        handle = os.open(temporary, flags, 0o600, dir_fd=fd)
        moved = False
        try:
            with os.fdopen(handle, 'wb') as stream:
                stream.write(png)
            if os.name == 'nt':
                os.rename(temporary, dest)  # unlike POSIX rename, refuses any existing target
                moved = True
            else:
                os.link(temporary, dest, src_dir_fd=fd, dst_dir_fd=fd)
        except FileExistsError as exc:
            raise ElementError('CROP_EXISTS', 'Choose a new PNG; never overwrite evidence.') from exc
        finally:
            if not moved:
                os.unlink(temporary, dir_fd=fd)


def _visible_box(meta, renderer, frozen):
    """Map PDFium's unrotated MediaBox/CropBox intersection into locator (display) space."""
    from pdfminer.pdftypes import resolve1

    w, h = meta.mediabox[2:]
    angle = resolve1(meta.attrs.get('Rotate', 0))
    if (meta.mediabox[:2] != (0, 0) or 'MediaBox' not in meta.attrs or
            resolve1(meta.attrs.get('UserUnit', 1)) != 1 or
            type(angle) not in (int, float) or angle % 90 or
            angle % 360 != renderer.get_rotation()):
        # Schema v1 saved dimensions but no MediaBox origin. pdfplumber versions
        # differ in handling offset origins; width/height alone cannot disambiguate.
        raise ElementError('CROP_GEOMETRY_UNSUPPORTED', 'Need zero-origin MediaBox, unit PDF points and matching orthogonal rotation.')
    angle %= 360
    expected = (h, w) if angle in (90, 270) else (w, h)
    if expected != (frozen['width'], frozen['height']):
        raise ElementError('CROP_GEOMETRY_UNSUPPORTED', 'MediaBox dimensions do not match the frozen locator page.')
    # Unlike individual PDFium get_*box getters, get_bbox handles inherited page boxes.
    l, b, r, t = renderer.get_bbox()
    crop = meta.cropbox
    visible = (max(0, crop[0]), max(0, crop[1]), min(w, crop[2]), min(h, crop[3]))
    if not (0 <= l < r and 0 <= b < t and all(math.isclose(a, v, rel_tol=0, abs_tol=0.001)
                                              for a, v in zip((l, b, r, t), visible))):
        raise ElementError('CROP_GEOMETRY_UNSUPPORTED', 'Render and native page boxes disagree.')
    # Use native double precision for locator boundaries; PDFium box values are float32.
    l, b, r, t = visible
    area = {0: (l, h-t, r, h-b), 90: (b, l, t, r),
            180: (w-r, b, w-l, t), 270: (h-t, w-r, h-b, w-l)}[angle]
    if not all(math.isclose(a, v, rel_tol=0, abs_tol=0.001) for a, v in
               zip(renderer.get_size(), (area[2]-area[0], area[3]-area[1]))):
        raise ElementError('CROP_GEOMETRY_UNSUPPORTED', 'Rendered dimensions do not match the rotated visible page.')
    return area


def _render(data, page_num, page_count, frozen, box, scale):
    try:
        import pypdfium2 as pdfium
        from pdfminer.pdfpage import PDFPage
        from PIL import Image  # Ensure the PNG encoder is provisioned before rendering.
    except (ImportError, OSError) as exc:
        raise ElementError('CROP_RENDERER_UNAVAILABLE', 'Use a provisioned Python with pdfminer.six, pypdfium2 and Pillow; nothing is installed automatically.') from exc

    try:
        # Read metadata only with the same page-tree semantics as pdfplumber. No extraction or OCR.
        meta = next(PDFPage.get_pages(BytesIO(data), pagenos={page_num-1}, check_extractable=True))
        if meta.doc.encryption:
            raise ElementError('PDF_ELEMENTS_ENCRYPTED', 'Encrypted sources cannot be rendered here.')
        with pdfium.PdfDocument(data) as doc:
            if len(doc) != page_count:
                raise ElementError('CROP_GEOMETRY_UNSUPPORTED', 'Rendered page count disagrees with frozen native pages.')
            with closing(doc[page_num-1]) as page:
                l, t, r, b = _visible_box(meta, page, frozen)
                x0, y0, x1, y1 = box
                if not (l <= x0 < x1 <= r and t <= y0 < y1 <= b):
                    raise ElementError('CROP_GEOMETRY_UNSUPPORTED', 'The requested locator bbox is not wholly visible in the PDF CropBox.')
                pw, ph = (math.ceil(d*scale) for d in page.get_size())
                if not (0 < pw <= MAX_SIDE and 0 < ph <= MAX_SIDE):
                    raise ElementError('CROP_LIMIT', 'Scaled virtual page exceeds the dimension limit.')
                # Match PDFium's full integer viewport. Round outward to enclose fractional edges.
                left, right = math.floor((x0-l)*pw/(r-l)), math.ceil((x1-l)*pw/(r-l))
                top, bottom = math.floor((y0-t)*ph/(b-t)), math.ceil((y1-t)*ph/(b-t))
                size = right-left, bottom-top
                if min(size) < 1 or size[0]*size[1] > MAX_PIXELS:
                    raise ElementError('CROP_LIMIT', 'Requested crop exceeds pixel limits.')
                # render() rounds each point margin UP to a pixel; choose an interior
                # value for that integer to avoid an off-by-one on float round trips.
                margins = tuple((n-0.5)/scale if n else 0 for n in (left, ph-bottom, pw-right, top))
                with closing(page.render(scale=scale, crop=margins, rev_byteorder=True,
                                         draw_annots=True, limit_image_cache=True)) as bitmap:
                    if (bitmap.width, bitmap.height) != size:
                        raise ElementError('CROP_GEOMETRY_UNSUPPORTED', 'Renderer did not honor the expected pixel rectangle.')
                    with bitmap.to_pil() as image, BytesIO() as buf:
                        image.save(buf, format='PNG')
                        return buf.getvalue(), list(size)
    except ElementError:
        raise
    except Exception as exc:
        raise ElementError('CROP_RENDER_FAILED', 'Could not render source page: '+type(exc).__name__) from exc


def render_crop(root, source_id, page_num, bbox, out, scale=2.0):
    """Render one 1-based physical page bbox [x0, top, x1, bottom] into a new run-local PNG."""
    root = Path(root).absolute()
    _check_path(root)
    root = root.resolve(strict=True)
    out = _relative(out)
    if len(out.parts) < 2 or out.parts[0] not in ('evidence', 'reviews') or out.suffix.lower() != '.png':
        raise ElementError('INVALID_ARGUMENT', 'Choose a new run-relative PNG under evidence/ or reviews/.')
    for directory in reversed(out.parents):
        _check_path(root/directory, missing_ok=True)
    if _check_path(root/out, missing_ok=True):
        raise ElementError('CROP_EXISTS', 'Choose a new PNG; never overwrite evidence.')
    if (type(page_num) is not int or page_num < 1 or not isinstance(source_id, str) or not source_id or
            type(scale) not in (int, float) or not MIN_SCALE <= scale <= MAX_SCALE):
        raise ElementError('INVALID_ARGUMENT', f'Use a source ID, positive integer physical page and scale {MIN_SCALE}..{MAX_SCALE}.')
    packet = load(root/'paper_packet.json')
    sources = [s for s in packet.get('sources', []) if s.get('access_state') == 'AVAILABLE']
    for source in sources:
        local = _relative(source['local_path'])
        for part in (*reversed(local.parents), local):
            _check_path(root/part, missing_ok=True)
    pages = _native(root, packet, source_id)
    if page_num not in pages:
        raise ElementError('INVALID_ARGUMENT', 'Select a physical page in the frozen source.')
    page_ref, page = pages[page_num]
    # Compare against finite page bounds before converting to float (also rejects huge ints).
    if (not all(0 < page[d] < math.inf for d in ('width', 'height')) or
            not isinstance(bbox, (list, tuple)) or len(bbox) != 4 or
            any(type(v) not in (int, float) for v in bbox) or
            not (0 <= bbox[0] < bbox[2] <= page['width'] and 0 <= bbox[1] < bbox[3] <= page['height'])):
        raise ElementError('INVALID_ARGUMENT', 'Use a positive finite bbox inside the locator page, in top-left PDF points.')
    selected = [s for s in sources if s['source_id'] == source_id]
    if len(selected) != 1:
        raise ElementError('ELEMENTS_INVALID', 'Expected exactly one available source with this identity.')
    source = selected[0]
    with (root/_relative(source['local_path'])).open('rb') as stream:
        size = os.fstat(stream.fileno()).st_size
        if size > MAX_SOURCE_BYTES:
            raise ElementError('CROP_LIMIT', 'Frozen source exceeds the native extraction byte limit.')
        data = stream.read(size+1)
    if len(data) != size or sha256(data).hexdigest() != source['sha256']:
        raise ElementError('ELEMENT_SOURCE_CHANGED', 'The bytes to render no longer match the frozen source.')
    png, size = _render(data, page_num, len(pages), page, bbox, scale)
    _publish(root, out, png)
    return {'source_id': source_id, 'source_sha256': source['sha256'], 'physical_page': page_num,
            'page_ref': page_ref, 'bbox': list(bbox), 'scale': scale, 'pixel_size': size,
            'path': out.as_posix(), 'image_sha256': sha256(png).hexdigest(),
            'ocr_used': False, 'reading_state_changed': False}
