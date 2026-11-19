"""Optional physical-page / bbox boundary for a single screening paper, not a filesystem sandbox."""
import math
from pathlib import Path

from reading_run_records import RunError, digest, read


def _box(value):
    return (isinstance(value, list) and len(value) == 4
            and all(type(x) in (int, float) and math.isfinite(x) for x in value)
            and 0 <= value[0] < value[2] and 0 <= value[1] < value[3])


def regions_for(record, page, bbox=None):
    """A request must fit inside one allowed rectangle; two disjoint grants do not grant their gap."""
    scope = record.get('reading_scope')
    if scope is None:
        return
    if scope['source_sha256'] != record['full_text'].get('current_sha256'):
        raise RunError('READING_SCOPE_STALE', 'Different source bytes. Remap the authorized section before reading.')
    if type(page) is int and (bbox is None or _box(bbox)):
        for row in scope['regions']:
            if row['physical_page'] != page:
                continue
            box = row.get('bbox')
            if box is None or (bbox is not None and box[0] <= bbox[0] and box[1] <= bbox[1]
                               and bbox[2] <= box[2] and bbox[3] <= box[3]):
                return
    raise RunError('READING_SCOPE_LIMIT', 'Outside the authorized page/region. Use the bound locators or ask the user before expanding.')


def block_unbounded(record, action):
    if record.get('reading_scope') is not None:
        raise RunError('READING_SCOPE_LIMIT', f'{action} is not a bounded read. Use read-pages --view text or render-crop within the recorded regions.')


def check_item(record, locator, refs, paper_dir):
    if record.get('reading_scope') is None:
        return
    pages = locator.get('physical_page')
    pages = pages if isinstance(pages, list) else [pages]
    if not pages:
        raise RunError('READING_SCOPE_LIMIT', 'An examined item needs a physical locator.')
    for page in pages:
        regions_for(record, page, locator.get('bbox'))
    if refs:
        sha = record['full_text']['current_sha256']
        ver = next(v for v in record['full_text']['versions'] if v['sha256'] == sha)
        folder = Path(paper_dir)/ver['directory']/'evidence'
        receipts = read(folder/'receipts.json', {})
        for ref in refs:
            path = (Path(paper_dir)/ref).resolve()
            receipt = receipts.get(path.name, {})
            if (path.parent != folder.resolve() or not path.is_file() or receipt.get('source_sha256') != sha
                    or receipt.get('image_sha256') != digest(path) or receipt.get('physical_page') not in pages):
                raise RunError('READING_SCOPE_LIMIT', 'A scoped image needs a matching render receipt for this item.')
            regions_for(record, receipt['physical_page'], receipt.get('bbox'))


def bind(record, spec, instruction, paper_dir):
    sha = record['full_text'].get('current_sha256')
    if not (isinstance(instruction, str) and instruction.strip() and isinstance(spec, dict) and sha
            and spec.get('source_sha256') == sha):
        raise RunError('INVALID_READING_SCOPE', 'Supply the actual user instruction and locators for the attached source hash.')
    if record.get('l3'):
        raise RunError('INVALID_READING_SCOPE', 'A screening boundary cannot narrow an existing complete-reading run.')
    previous = record.get('reading_scope')
    if previous and spec != {'source_sha256': previous['source_sha256'], 'regions': previous['regions']} and instruction.strip() == previous['user_instruction'].strip() and previous['source_sha256'] == sha:
        raise RunError('INVALID_READING_SCOPE', 'Changing these regions needs the new user instruction, not the original restriction.')
    if spec.get('whole_paper') is True and set(spec) == {'whole_paper', 'source_sha256'} and previous:
        record.setdefault('reading_scope_history', []).append({**record.pop('reading_scope'), 'released_by': instruction})
        return
    rows = spec.get('regions')
    if not isinstance(rows, list) or not rows or any(
            not isinstance(r, dict) or set(r) - {'physical_page', 'bbox'} or type(r.get('physical_page')) is not int
            or r['physical_page'] <= 0 or ('bbox' in r and not _box(r['bbox'])) for r in rows):
        raise RunError('INVALID_READING_SCOPE', 'Map the section to positive physical pages and optional finite PDF bboxes.')
    scope = {'schema_version': 1, 'source_sha256': sha, 'regions': rows, 'user_instruction': instruction}
    # Do not silently re-authorize already recorded, unlocated material under a narrower scope.
    candidate = dict(record, reading_scope=scope)
    for row in record['passes']:
        if row.get('status') == 'CURRENT' and row.get('source_sha256') == sha:
            for item in row['examined']:
                if 'locator' in item:
                    check_item(candidate, item['locator'], item.get('artifact_refs'), paper_dir)
    if record.get('reading_scope'):
        record.setdefault('reading_scope_history', []).append(record['reading_scope'])
    record['reading_scope'] = scope
