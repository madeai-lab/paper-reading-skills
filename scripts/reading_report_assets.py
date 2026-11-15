"""Build a local Markdown figure gallery from inspected source-image records."""
import argparse
import html
import json
from pathlib import Path
from urllib.parse import quote

from reading_run_records import RunError, read, write

MARKER = '<!-- generated-reading-report-visuals -->'


def label(text):
    return html.escape(str(text)).replace('[', '&#91;').replace(']', '&#93;').replace('\n', ' ')


def build_gallery(root, manifest):
    root = Path(root).resolve()
    packet = read(root/'paper_packet.json')
    units = {u['unit_id']: u for u in packet['units']}
    claims = {c['claim_id'] for c in packet.get('claims', [])}
    if not isinstance(manifest, list) or not manifest:
        raise RunError('INVALID_VISUAL', 'Provide a nonempty visual-record array.')
    ids = set()
    lines = ['# Report visual evidence', '', MARKER, '',
             'Display aid only; inspect the sources and current independent review before relying on claims.', '']
    for item in manifest:
        required = {'visual_id', 'kind', 'title', 'unit_refs', 'artifact_refs',
                    'caption', 'interpretation', 'limitations', 'claim_refs'}
        if not isinstance(item, dict) or not required <= item.keys():
            raise RunError('INVALID_VISUAL', 'Incomplete visual record.')
        for key in ['visual_id', 'title', 'caption', 'interpretation', 'limitations']:
            if not isinstance(item[key], str) or not item[key].strip():
                raise RunError('INVALID_VISUAL', 'Nonempty visual text required: '+key)
        if item['kind'] != 'SOURCE_IMAGE' or item['visual_id'] in ids:
            raise RunError('INVALID_VISUAL', 'Use unique IDs and SOURCE_IMAGE records for this helper.')
        ids.add(item['visual_id'])
        for key in ['unit_refs', 'artifact_refs', 'claim_refs']:
            if not isinstance(item[key], list) or any(not isinstance(x, str) for x in item[key]):
                raise RunError('INVALID_VISUAL', key+' must be an array of strings.')
        if not item['unit_refs'] or not item['artifact_refs'] or set(item['unit_refs'])-units.keys() or set(item['claim_refs'])-claims:
            raise RunError('INVALID_VISUAL', 'Reference existing units, images and claims.')
        inspected = set()
        locators = []
        for uid in item['unit_refs']:
            unit = units[uid]
            visual = unit.get('visual_review', {})
            if visual.get('actually_viewed') is not True or not unit.get('locators'):
                raise RunError('INVALID_VISUAL', 'Actual source viewing and locators required: '+uid)
            inspected.update(visual.get('artifact_refs', []))
            locators.append({'unit_id': uid, 'source_id': unit.get('source_id'), 'locators': unit['locators']})
        lines += ['## '+label(item['visual_id']+' — '+item['title']), '']
        for ref in item['artifact_refs']:
            path = (root/ref).resolve()
            if (not path.is_relative_to(root) or path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}
                    or not path.is_file() or not path.stat().st_size or ref not in inspected):
                raise RunError('INVALID_VISUAL', 'Use an existing in-run image registered as actually inspected: '+ref)
            url = quote(path.relative_to(root).as_posix(), safe='/')
            lines += ['!['+label(item['title'])+']('+url+')', '', '[Open full resolution]('+url+')', '']
        lines += ['**Caption:** '+label(item['caption']), '',
                  '**Interpretation:** '+label(item['interpretation']), '',
                  '**Limitations:** '+label(item['limitations']), '',
                  '**Claim references:** '+label(', '.join(item['claim_refs']) or 'None'), '',
                  '**Source locators:**', '', '```json',
                  json.dumps(locators, ensure_ascii=False, indent=2), '```', '']
    derived = [row for row in packet.get('report_visuals', []) if row.get('kind') != 'SOURCE_IMAGE']
    if ids & {row.get('visual_id') for row in derived}:
        raise RunError('INVALID_VISUAL', 'Source image IDs must not collide with retained derived visuals.')
    # Validate the whole manifest before mutating any run records.
    output = root/'report_visuals.md'
    if output.exists() and MARKER not in output.read_text(encoding='utf8'):
        raise RunError('OUTPUT_EXISTS', 'Preserve the existing report_visuals.md; move it explicitly before generation.')
    output.write_text('\n'.join(lines), encoding='utf8')
    packet['report_visuals'] = manifest + derived
    packet['deliverables']['report_visuals'] = 'report_visuals.md'
    write(root/'paper_packet.json', packet)
    return {'path': 'report_visuals.md', 'visual_count': len(manifest),
            'notice': 'Generated display only; changed report/assets require actual review. No read states or gates were promoted.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_directory', type=Path)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(build_gallery(args.run_directory, read(args.manifest)), ensure_ascii=True, indent=2))
        return 0
    except (RunError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'error_code': getattr(exc, 'code', 'RECORD_ERROR'), 'message': str(exc)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
