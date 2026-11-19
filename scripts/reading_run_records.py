"""Canonical record I/O, content fingerprints and generated reading documents."""
import copy
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

from reading_data_sources import data_paths, registered_data
import reading_repair_sync as repair_sync

MARKER = "<!-- generated-reading-records -->"


class RunError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def read(path, default=None):
    if not path.exists() and default is not None:
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    temp.replace(path)


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def evidence(root, refs):
    return bool(refs) and all(isinstance(x, str) and (root / x.split("#", 1)[0]).is_file() for x in refs)


def inline_image_refs(root, documents, raw_sources):
    root = root.resolve()
    for ref in documents:
        document = root/ref
        if document.suffix.lower() != '.md' or not document.is_file() or document.resolve() in raw_sources:
            continue
        for match in re.finditer(r'!\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"]*")?\)', document.read_text(encoding='utf-8-sig')):
            destination = unquote(match[1].strip('<>').split('#', 1)[0])
            if destination and not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', destination) and not destination.startswith('data:'):
                yield (document.parent/destination).resolve().relative_to(root).as_posix()


def content_fingerprint(root, packet):
    """Bind new snapshots to the inspected records and local evidence, excluding decisions."""
    return next(_content_fingerprints(root, packet))


def review_content_matches(root, packet, review):
    expected = review.get('reviewed_content_sha256')
    candidates = _content_fingerprints(root, packet)
    return expected == next(candidates) or (review in packet.get('reviews', []) and expected in candidates)


def _content_fingerprints(root, packet):
    root = Path(root).resolve()
    keys = ['scope_mode','scope_revision','scope_exclusions','sources','units',
            'methods_taxonomy','experiments','claims','issues','owner_id','writer_ids']
    data = {key:packet.get(key) for key in keys}
    # Optional extensions leave legacy snapshots unchanged until actually used.
    for key in ['research_target', 'report_visuals', 'review_requirements', 'review_mode', 'content_acquisition']:
        if packet.get(key) is not None:
            data[key] = packet[key]
    data['inventory'] = read(root/'01_inventory.json', [])
    data['source_inventory'] = read(root/'01_sources.json', packet.get('sources',[]))
    refs = set()
    def collect(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in {'evidence_refs','artifact_refs','page_refs','conflict_resolution_refs'} and isinstance(item,list):
                    refs.update(x.split('#',1)[0] for x in item if isinstance(x,str))
                elif key == 'manifest_ref' and isinstance(item, str):
                    refs.add(item.split('#',1)[0])
                else:
                    collect(item)
        elif isinstance(value,list):
            for item in value:
                collect(item)
    collect(data)
    collect([packet.get('gate_results',{}).get(g,{}) for g in ['G0','G1','G2']])
    refs.update(s.get('local_path') for s in packet.get('sources',[]) if s.get('local_path'))
    refs.update(packet.get('deliverables',{}).get(key) for key in
                ['report','user_review','full_notebook','material_index',
                 'report_visuals','target_analysis','report_readability'])
    quality_ref = packet.get('deliverables', {}).get('report_readability')
    if isinstance(quality_ref, str):
        quality_path = (root / quality_ref).resolve()
        quality_path.relative_to(root.resolve())
        if quality_path.is_file():
            # Display screenshots are evidence bytes, even when not text documents.
            collect(read(quality_path))
    for source in registered_data(packet):
        provenance = source.get('provenance')
        if isinstance(provenance, dict) and isinstance(provenance.get('acquisition_ref'), str):
            refs.add(provenance['acquisition_ref'])
    refs = {ref for ref in refs if isinstance(ref, str)}
    images = set(inline_image_refs(root, refs, data_paths(root, packet)))
    files = {}
    for ref in sorted(refs | images):
        path = (root/ref).resolve()
        # The canonical JSON is represented above; review/state files are outputs.
        if path in {root/name for name in ['paper_packet.json','execution_state.json','01_inventory.json','01_sources.json']}:
            continue
        files[ref] = digest(path) if path.is_file() else 'MISSING'
    data['files'] = files
    if packet.get('review_requirements', {}).get('repair_dependency_sync'):
        data['current_documents'] = {name: repair_sync.sha(text.encode('utf8'))
                                     for name, text in repair_sync.current_documents(root, packet).items()}
    def snapshot():
        return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode('utf8')).hexdigest()

    yield snapshot()
    if images:
        # Stored pre-fix approvals used absolute image keys in addition to explicit evidence refs.
        legacy = {key: value for key, value in files.items() if key in refs}
        legacy.update({str(root/key): files[key] for key in images if key in files})
        data['files'] = legacy
        yield snapshot()


def generated_target(root, requested, fallback):
    target = (root/requested).resolve()
    number = 0
    while True:
        if not target.is_relative_to(root) or target.suffix.lower() != '.md':
            raise RunError('INVALID_PATH','Generated Markdown must stay inside the run directory.')
        if not target.exists() or MARKER in target.read_text(encoding='utf8'):
            return target
        name = fallback+'.md' if number==0 else f'{fallback}_{number}.md'
        target = (root/name).resolve()
        number += 1


def render(root, packet, check_only=False):
    target = generated_target(root,packet['deliverables'].get('full_notebook','full_notebook.md'),'unit_notebook')
    index_target = generated_target(root,'material_index.md','material_index')
    lines = ["# Source-unit reading notebook","",MARKER,"",
             "Generated from submitted records; rendering and blank entries do not establish reading.",""]
    index = ["# Source-unit index",'',MARKER,""]
    for unit in packet.get("units",[]):
        uid = unit["unit_id"]
        lines += [f"## {uid}","",f'**{unit.get("label",uid)}** — {unit.get("read_state","INVENTORIED")}',"",
                  unit.get("understanding_note") or "Pending source explanation.","",
                  "Source locators: "+json.dumps(unit.get("locators",[]),ensure_ascii=False),""]
        lines += [f"- [{ref}]({ref})" for ref in unit.get("evidence_refs",[])]
        details = {k:v for k,v in unit.items() if k not in {'understanding_note','locators','evidence_refs'}}
        lines += ['',chr(96)*3+'json',json.dumps(details,ensure_ascii=False,indent=2),chr(96)*3]
        lines += [""]
        index += [f'- [{uid}: {unit.get("label",uid)}]({target.relative_to(root).as_posix()}#{uid.lower()})']
    for key in ["methods_taxonomy","experiments","claims","issues"]:
        lines += [f"## {key}","",chr(96)*3+"json",json.dumps(packet.get(key,[]),ensure_ascii=False,indent=2),chr(96)*3,""]
    expected = {target: "\n".join(lines), index_target: "\n".join(index)+"\n"}
    if check_only:
        return [str(path.relative_to(root)) for path, text in expected.items()
                if not path.is_file() or path.read_text(encoding='utf8') != text]
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text("\n".join(lines),encoding="utf8")
    index_target.write_text("\n".join(index)+"\n",encoding="utf8")
    packet["deliverables"].update({'full_notebook':target.relative_to(root).as_posix(),
                                    'material_index':index_target.relative_to(root).as_posix()})
