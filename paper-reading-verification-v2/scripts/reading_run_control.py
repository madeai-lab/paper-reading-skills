"""Canonical paper-reading handoffs and terminal assessment; no model launcher."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil

from reading_run_check import inspect_run, VERIFIED

REVISION = "2.2"
VISUAL = {"FIGURE", "PANEL", "TABLE", "OTHER_VISUAL"}
STATES = {"INVENTORIED", "READ", "UNDERSTOOD", "CHECKED", "BLOCKED", "NON_INFORMATIVE", "OUT_OF_SCOPE"}
EXPERIMENT_FIELDS = set("experiment_id purpose unit_refs design data_and_sampling split ground_truth models_and_tools comparators budget metrics results uncertainty negative_results failure_cases limitations claim_refs".split())
STATE_FIELDS = set("owner_id writer_ids stage paper_status scope_revision open_unit_ids next_actions blockers stop_reason restart_action history".split())
PLACEHOLDERS = {"see figure", "understood", "correct",
                "see full_notebook.md; granular evidence still being developed."}
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


def pending(packet):
    excluded = {x["unit_id"] for x in packet.get("scope_exclusions", [])
                if packet.get("scope_mode") == "USER_DEFINED_SCOPE"}
    return [u for u in packet.get("units", []) if u.get("read_state") not in {"CHECKED", "NON_INFORMATIVE"}
            and not (u.get("unit_id") in excluded and u.get("read_state") == "OUT_OF_SCOPE")]


def requests(review, owner):
    result = []
    for index, item in enumerate(review.get("repair_requests", []), 1):
        row = copy.deepcopy(item) if isinstance(item, dict) else {"required_action": item}
        row.setdefault("repair_id", f'{review.get("review_id", "review")}-{index:02}')
        row.setdefault("unit_ids", [])
        row.setdefault("responsible_role", owner)
        result.append(row)
    return result


def content_fingerprint(root, packet):
    """Bind review to the inspected records and local evidence, excluding decisions."""
    keys = ['scope_mode','scope_revision','scope_exclusions','sources','units',
            'methods_taxonomy','experiments','claims','issues','owner_id','writer_ids']
    data = {key:packet.get(key) for key in keys}
    data['inventory'] = read(root/'01_inventory.json', [])
    data['source_inventory'] = read(root/'01_sources.json', packet.get('sources',[]))
    refs = set()
    def collect(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in {'evidence_refs','artifact_refs'} and isinstance(item,list):
                    refs.update(x.split('#',1)[0] for x in item if isinstance(x,str))
                else:
                    collect(item)
        elif isinstance(value,list):
            for item in value:
                collect(item)
    collect(data)
    collect([packet.get('gate_results',{}).get(g,{}) for g in ['G0','G1','G2']])
    refs.update(s.get('local_path') for s in packet.get('sources',[]) if s.get('local_path'))
    refs.update(packet.get('deliverables',{}).get(key) for key in
                ['report','user_review','full_notebook','material_index'])
    files = {}
    for ref in sorted(x for x in refs if isinstance(x,str)):
        path = (root/ref).resolve()
        # The canonical JSON is represented above; review/state files are outputs.
        if path in {root/name for name in ['paper_packet.json','execution_state.json','01_inventory.json','01_sources.json']}:
            continue
        files[ref] = digest(path) if path.is_file() else 'MISSING'
    data['files'] = files
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode('utf8')).hexdigest()


def current_review(root, packet, review):
    hashes = {s["source_id"]:s.get("sha256") for s in packet.get("sources", [])}
    return (review.get("reviewed_scope_revision") == packet.get("scope_revision")
            and review.get("reviewed_source_hashes") == hashes
            and review.get('reviewed_content_sha256') == content_fingerprint(root,packet))


def continue_with(kind, ids=None, **kwargs):
    return {"terminal_decision":"CONTINUE", "may_send_final":False, "paper_accepted":False,
            "next_action":{"kind":kind, "unit_ids":ids or [], **kwargs},
            "notice":"Perform the next action. This tool cannot intercept a host final message or prove understanding."}


def assess(root):
    packet, state = read(root/"paper_packet.json", {}), read(root/"execution_state.json", {})
    units = pending(packet)
    if not STATE_FIELDS <= state.keys():
        return continue_with("REPAIR_STATE_SCHEMA", [u.get("unit_id") for u in units[:4]],
                             required_fields=sorted(STATE_FIELDS-state.keys()))
    interrupt = state.get("interruption", {})
    reason = state.get("stop_reason")
    substantiated = (isinstance(interrupt, dict) and evidence(root, interrupt.get("evidence_refs"))
                     and interrupt.get("observed_constraint") and interrupt.get("attempts")
                     and state.get("restart_action"))
    blocked = set(interrupt.get("affected_unit_ids", [])) if isinstance(interrupt, dict) else set()
    accessible = [u for u in units if u.get("unit_id") not in blocked]
    latest = packet.get("reviews", [])[-1] if packet.get("reviews") else None
    progress = state.get('repair_progress',{})
    active = [r for r in requests(latest,state['owner_id']) if not (
        progress.get(r['repair_id'],{}).get('status') == 'READY_FOR_REVIEW'
        and progress[r['repair_id']].get('review_id') == latest.get('review_id')
        and progress[r['repair_id']].get('request_sha256') == hashlib.sha256(json.dumps(r,sort_keys=True,ensure_ascii=False).encode('utf8')).hexdigest()
        and progress[r['repair_id']].get('scope_revision') == packet.get('scope_revision'))] if latest and latest.get('decision') in {'REVISION_REQUIRED','MATERIAL_BLOCKED'} else []
    affected_repairs = set(interrupt.get('affected_repair_ids',[])) if isinstance(interrupt,dict) else set()
    accessible_repairs = [r for r in active if r['repair_id'] not in affected_repairs]
    checkpoint = (evidence(root,[packet.get('deliverables',{}).get('report')])
                  and evidence(root,[packet.get('deliverables',{}).get('user_review')]))
    capability_block = (reason=='CAPABILITY_BLOCK' and not units and not active
        and interrupt.get('affected_action')=='REQUEST_REVIEW' and packet.get('claims')
        and all(packet.get('gate_results',{}).get(g,{}).get('decision')=='PASS' for g in ['G0','G1','G2']))
    material_block = (reason=='MATERIAL_BLOCK' and bool(blocked) and bool(units)
        and all(u.get('read_state')=='BLOCKED' for u in units)
        and not accessible and not accessible_repairs)
    allowed = reason in {'USER_STOP','RESOURCE_LIMIT'} or (checkpoint and (capability_block or material_block))
    if substantiated and allowed:
        return {"terminal_decision":"INTERRUPTED_WITH_EVIDENCE", "may_send_final":True,
                "paper_accepted":False, "stop_reason":reason, "restart_action":state["restart_action"],
                "notice":"The agent must verify the actual user/platform/material constraint; a record alone cannot authenticate it."}
    if latest and latest.get("decision") in {"REVISION_REQUIRED","MATERIAL_BLOCKED"}:
        if accessible_repairs:
            batch = accessible_repairs[:3]
            ids = list(dict.fromkeys(uid for item in batch for uid in item["unit_ids"]))
            return continue_with("REPAIR",ids, repair_ids=[r["repair_id"] for r in batch], requests=batch,
                                 instruction="Inspect source and repair affected records/dependencies; save repair evidence and obtain reviewer reinspection.")
    if packet.get("gate_results",{}).get("G0",{}).get("decision") != "PASS":
        return continue_with("SOURCE_INVENTORY", instruction="Inspect source identity/all pages; save source inventory before dependent readers, then merge an evidenced G0 decision.")
    if accessible:
        return continue_with("READ_AND_RECORD_UNITS", [u.get("unit_id") for u in accessible[:4]],
                             units=accessible[:4], open_unit_count=len(units),
                             instruction="Actually read/check these units and submit their own source-specific explanations; do not defer detail or merely change flags.")
    if units:
        return continue_with("RESOLVE_READING_GAPS",[u.get("unit_id") for u in units[:4]],
                             instruction="Record actual blocked units and evidence. Do not invent a limit.")
    for gate in ["G1","G2"]:
        if packet.get("gate_results",{}).get(gate,{}).get("decision") != "PASS":
            return continue_with("VERIFY_LOCAL_GATE",gate=gate,
                                 instruction="Check source coverage and semantic relationships; submit actual evidence, not a flag-only repair.")
    if not packet.get("claims"):
        return continue_with("WRITE_CLAIM_RECORDS", instruction="Record important claims, attribution, source units, conditions and restrictions.")
    for key in ["report","user_review"]:
        if not evidence(root,[packet.get("deliverables",{}).get(key)]):
            return continue_with("WRITE_REPORT_PACKAGE", missing=key,
                                 instruction="Write the readable report/issue packet from complete records, then continue to full independent review.")
    if not latest or latest.get("decision") not in VERIFIED or not current_review(root,packet,latest):
        return continue_with("REQUEST_REVIEW", instruction="Use the distinct source-first reviewer for this current full packet; ingest its actual decision and act on failed review.")
    errors = inspect_run(root)
    if errors:
        return continue_with("REPAIR_RECORDS",errors=errors[:6],error_count=len(errors),
                             instruction="Repair actual work or specific inconsistent records, then assess again.")
    if state.get("open_unit_ids") or state.get("paper_status") != packet.get("paper_status"):
        return continue_with("SYNC_STATE",instruction="Sync canonical state from current evidence without changing review decisions.")
    return {"terminal_decision":"ACCEPTED", "may_send_final":True, "paper_accepted":True,
            "next_action":{"kind":"FINAL_DELIVERY","unit_ids":[]},
            "notice":"Recorded independent acceptance and structural consistency, not automated scientific certification."}


def sync_inventory(root, packet, state):
    inventory = read(root/"01_inventory.json", [])
    ids = [u.get("unit_id") for u in inventory]
    if any(not isinstance(uid,str) or not re.fullmatch(r"[A-Za-z0-9_.-]+",uid) for uid in ids) or len(ids)!=len(set(ids)):
        raise RunError("INVALID_INVENTORY","Unit IDs must be unique safe strings.")
    if set(state.get("inventory_ids",[]))-set(ids):
        raise RunError("INVENTORY_REMOVAL","Retain inventoried IDs; explicit user exclusions use OUT_OF_SCOPE.")
    fields = ["unit_id","kind","label","source_id","locators","parent_id","children"]
    fingerprint = hashlib.sha256(json.dumps([{k:u.get(k) for k in fields} for u in inventory],
                                            sort_keys=True,ensure_ascii=False).encode("utf8")).hexdigest()
    inventory_changed = bool(state.get('inventory_fingerprint') and fingerprint != state['inventory_fingerprint'])
    if inventory_changed:
        packet["scope_revision"] = packet.get("scope_revision",1)+1
        state["history"].append("Inventory changed; prior review requires reinspection.")
    state["inventory_ids"], state["inventory_fingerprint"] = ids, fingerprint
    old_hashes = {s["source_id"]:s.get("sha256") for s in packet.get("sources",[])}
    sources = read(root/"01_sources.json") if (root/"01_sources.json").exists() else packet.get("sources",[])
    new_hashes = {s["source_id"]:s.get("sha256") for s in sources}
    changed_sources = {sid for sid in old_hashes if old_hashes[sid] != new_hashes.get(sid)}
    if changed_sources and not inventory_changed:
        packet["scope_revision"] = packet.get("scope_revision",1)+1
        state["history"].append("Source hashes changed; dependent units require new reading/checking.")
    known = {u["unit_id"]:u for u in packet.get("units",[])}
    merged = []
    for item in inventory:
        unit = copy.deepcopy(known.get(item["unit_id"],item))
        prior = known.get(item["unit_id"])
        changed = prior is not None and (any(prior.get(k)!=item.get(k) for k in fields)
                                         or prior.get("source_id") in changed_sources)
        for key in fields+["assigned_owner"]:
            if key in item:
                unit[key] = copy.deepcopy(item[key])
        if item["unit_id"] not in known:
            unit.update({"read_state":"INVENTORIED","understanding_note":None,"evidence_refs":[],
                         "visual_review":{"required":item.get("kind") in VISUAL,"actually_viewed":False,
                                          "artifact_refs":[],"checks":[],"limitations":[]}})
        elif changed:
            unit["read_state"] = "READ"
            unit.setdefault("visual_review",{})["actually_viewed"] = False
        merged.append(unit)
    packet["units"] = merged
    packet["sources"] = sources


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


def render(root, packet):
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
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text("\n".join(lines),encoding="utf8")
    index_target.write_text("\n".join(index)+"\n",encoding="utf8")
    packet["deliverables"].update({'full_notebook':target.relative_to(root).as_posix(),
                                    'material_index':index_target.relative_to(root).as_posix()})


def commit(root, packet, state, event):
    state.update({"skill_revision":REVISION,"scope_revision":packet["scope_revision"],
                  "paper_status":packet["paper_status"],"writer_ids":packet["writer_ids"],
                  "open_unit_ids":[u["unit_id"] for u in pending(packet)],
                  "source_versions":packet.get("sources",[])})
    state["history"].append(event)
    render(root,packet)
    write(root/"paper_packet.json",packet)
    write(root/"execution_state.json",state)
    result = assess(root)
    state["next_actions"] = [result["next_action"]] if result.get("next_action") else []
    write(root/"execution_state.json",state)
    return result


def initialize(root, source, owner, language):
    if root.exists():
        raise RunError("RUN_EXISTS","Choose a new output directory; existing runs are never overwritten.")
    source = source.resolve()
    with source.open("rb") as stream:
        if stream.read(5)!=b"%PDF-":
            raise RunError("INVALID_SOURCE","Input does not have a PDF header.")
    templates = Path(__file__).resolve().parent.parent/"shared"
    packet,state,task = [read(templates/name) for name in ["packet.template.json","execution-state.template.json","task.template.json"]]
    src = {"source_id":"SRC-01","title":None,"version":None,"publication_status":None,
           "local_path":"source.pdf","sha256":digest(source),"page_count":None,"access_state":"AVAILABLE",
           "required_for_scope":True,"supplement_of":None,"missing_reason":None}
    root.mkdir(parents=True)
    shutil.copyfile(source,root/"source.pdf")
    packet.update({"template_only":False,"skill_revision":REVISION,"task_id":root.name,"paper_id":root.name,
                   "owner_id":owner,"writer_ids":[owner],"paper_status":"IN_PROGRESS","sources":[src]})
    packet["deliverables"] = {k:k+".md" for k in ["full_notebook","report","material_index","user_review","independent_review"]}
    state.update({"template_only":False,"skill_revision":REVISION,"task_id":root.name,"owner_id":owner,
                  "writer_ids":[owner],"stage":"01","paper_status":"IN_PROGRESS","repair_progress":{}})
    task.update({"template_only":False,"skill_revision":REVISION,"task_id":root.name,"paper_id":root.name,
                 "language":language,"source_files":["source.pdf"],"output_dir":str(root),"source_root":str(root)})
    for name,value in [("task.json",task),("assignment_map.json",{"owner":owner,"roles":{},"review_capacity":"PLAN_AT_STARTUP"}),
                       ("01_inventory.json",[]),("01_sources.json",[src])]:
        write(root/name,value)
    return commit(root,packet,state,"Initialized canonical records; source identity/reading still require inspection.")


def merge_handoff(root, payload):
    packet,state = read(root/"paper_packet.json"),read(root/"execution_state.json")
    sync_inventory(root,packet,state)
    writer = payload.get("writer_id")
    if not writer:
        raise RunError("INVALID_HANDOFF","Actual writer_id is required.")
    allowed = {"writer_id","units","methods_taxonomy","experiments","claims","issues","gate_results"}
    if payload.keys()-allowed:
        raise RunError("INVALID_HANDOFF","Unknown handoff fields: "+", ".join(sorted(payload.keys()-allowed)))
    units = {u["unit_id"]:u for u in packet["units"]}
    submitted = set()
    for item in payload.get("units",[]):
        uid = item.get("unit_id")
        if uid not in units:
            raise RunError("INVALID_HANDOFF","Inventory this source unit first: "+str(uid))
        if uid in submitted:
            raise RunError("INVALID_HANDOFF","Duplicate unit in one handoff: "+uid)
        submitted.add(uid)
        for key in ["kind","source_id","label","parent_id","children","locators"]:
            if key in item and item[key] != units[uid].get(key):
                raise RunError("INVALID_HANDOFF","Source identity/locator changes belong in the inventory, not a reading handoff: "+uid)
        unit = {**units[uid],**copy.deepcopy(item)}
        note = unit.get("understanding_note")
        if not isinstance(note,str) or not note.strip() or note.strip().lower() in PLACEHOLDERS:
            raise RunError("INVALID_HANDOFF","Submit a source-specific explanation for "+uid)
        if unit.get("read_state") not in STATES:
            raise RunError("INVALID_HANDOFF","Invalid read_state for "+uid)
        if unit["read_state"] in {"UNDERSTOOD","CHECKED","NON_INFORMATIVE"}:
            if not unit.get("locators") or not evidence(root,unit.get("evidence_refs")):
                raise RunError("INVALID_HANDOFF","Missing source locators/evidence for "+uid)
            if unit.get("kind") in VISUAL and unit.get("visual_review",{}).get("actually_viewed") is not True:
                raise RunError("INVALID_HANDOFF","Actually view this informative visual before claiming understanding: "+uid)
        units[uid] = unit
    packet["units"] = list(units.values())
    for key,id_field in [("methods_taxonomy","method_id"),("experiments","experiment_id"),("claims","claim_id"),("issues","issue_id")]:
        existing = {x[id_field]:x for x in packet.get(key,[])}
        for item in payload.get(key,[]):
            if not item.get(id_field):
                raise RunError("INVALID_HANDOFF",key+" needs "+id_field)
            if key=="experiments" and not EXPERIMENT_FIELDS<=item.keys():
                raise RunError("INVALID_HANDOFF","Incomplete experiment fields: "+", ".join(sorted(EXPERIMENT_FIELDS-item.keys())))
            existing[item[id_field]] = copy.deepcopy(item)
        packet[key] = list(existing.values())
    for gate,value in payload.get("gate_results",{}).items():
        if gate not in {"G0","G1","G2"} or writer!=packet["owner_id"]:
            raise RunError("INVALID_HANDOFF","Only Owner G0–G2 decisions can be merged; actual independent review supplies G3.")
        if value.get("decision") not in {"PASS","FAIL","PENDING"} or "status" in value:
            raise RunError("INVALID_HANDOFF","Gate uses decision, not status.")
        if value["decision"]=="PASS" and (value.get("open_items") or not evidence(root,value.get("evidence_refs"))):
            raise RunError("INVALID_HANDOFF","PASS requires actual evidence and no open items.")
        if gate=="G0" and value["decision"]=="PASS" and (not packet["units"] or not packet.get("sources")):
            raise RunError("INVALID_HANDOFF","G0 requires a real nonempty source inventory.")
        if gate in {"G1","G2"} and value["decision"]=="PASS" and pending(packet):
            raise RunError("INVALID_HANDOFF","Complete actual unit reading/checking before G1/G2.")
        packet["gate_results"][gate] = copy.deepcopy(value)
    if writer not in packet["writer_ids"]:
        packet["writer_ids"].append(writer)
    payload_hash = hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode("utf8")).hexdigest()
    write(root/"handoffs"/(payload_hash+".json"),payload)
    return commit(root,packet,state,"Merged actual handoff from "+writer+"; read states were not automatically promoted.")


def ingest_review(root, review):
    packet,state = read(root/"paper_packet.json"),read(root/"execution_state.json")
    if (not isinstance(review.get('review_id'),str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',review['review_id'])
            or not review.get("reviewer_id") or review.get("template_only") is True
            or review.get("decision") not in VERIFIED|{"REVISION_REQUIRED","MATERIAL_BLOCKED"}):
        raise RunError("INVALID_REVIEW","Actual reviewer identity, stable review_id and decision are required.")
    if review["reviewer_id"] in packet.get("writer_ids",[]):
        raise RunError("INVALID_REVIEW","Reviewer must be distinct from actual writers.")
    if review["decision"] in VERIFIED and (not current_review(root,packet,review) or review.get("repair_requests")
            or review.get("unresolved_reading_gaps")
            or any(review.get("gate_decisions",{}).get(g)!="PASS" for g in ["G0","G1","G2","G3"])):
        raise RunError("INVALID_REVIEW","Accepted review must cover current sources/scope and close repair requests.")
    reviews = packet.setdefault("reviews",[])
    old = next((r for r in reviews if r.get("review_id")==review["review_id"]),None)
    if old is not None:
        if old!=review:
            raise RunError("INVALID_REVIEW","Use a new review_id for a changed decision; preserve history.")
    else:
        reviews.append(copy.deepcopy(review))
    rid = review['review_id']
    ref = "reviews/"+rid+".json"
    write(root/ref,review)
    packet["gate_results"]["G3"] = {"decision":review.get("gate_decisions",{}).get("G3","PENDING"),
                                   "evidence_refs":[ref],"open_items":[r["repair_id"] for r in requests(review,packet["owner_id"])]}
    for gate in ["G0","G1","G2"]:
        if review.get("gate_decisions",{}).get(gate) in {"FAIL","PENDING"}:
            packet["gate_results"][gate] = {"decision":review["gate_decisions"][gate],"evidence_refs":[ref],
                                           "open_items":["Reviewer requires repair/reinspection."]}
    packet["paper_status"] = review["decision"]
    state["stage"] = "08"
    state["review_plan"] = {"reviewer_id":review["reviewer_id"],"status":review["decision"],
                            "source_first_inventory_ref":review.get("source_first_inventory_ref")}
    return commit(root,packet,state,"Actual review returned "+review["decision"]+"; Owner must act on remaining requests.")


def repair_ready(root, repair_id, ref):
    packet,state = read(root/"paper_packet.json"),read(root/"execution_state.json")
    latest = packet.get("reviews",[])[-1] if packet.get("reviews") else {}
    request = next((r for r in requests(latest,packet['owner_id']) if r['repair_id']==repair_id),None)
    if request is None or not evidence(root,[ref]):
        raise RunError("INVALID_REPAIR","Use a latest-review repair ID and existing repair evidence.")
    state.setdefault("repair_progress",{})[repair_id] = {"status":"READY_FOR_REVIEW",
        "scope_revision":packet["scope_revision"],"review_id":latest.get('review_id'),
        "request_sha256":hashlib.sha256(json.dumps(request,sort_keys=True,ensure_ascii=False).encode('utf8')).hexdigest(),
        "evidence_refs":[ref]}
    return commit(root,packet,state,"Saved repair evidence for "+repair_id+"; reviewer reinspection is still required.")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["init","merge","ingest-review","repair-ready","sync","next","snapshot"])
    parser.add_argument("run_directory",type=Path)
    parser.add_argument("--source",type=Path)
    parser.add_argument("--owner",default="root")
    parser.add_argument("--language",choices=["zh-CN","en"],default="zh-CN")
    parser.add_argument("--file",type=Path)
    parser.add_argument("--id")
    parser.add_argument("--evidence")
    args=parser.parse_args()
    root=args.run_directory.resolve()
    try:
        if args.command=="init":
            if args.source is None:
                raise RunError("INVALID_ARGUMENT","init needs --source.")
            result=initialize(root,args.source,args.owner,args.language)
        elif args.command=="next":
            result=assess(root)
        elif args.command=='snapshot':
            packet=read(root/'paper_packet.json')
            result={'reviewed_scope_revision':packet.get('scope_revision'),
                    'reviewed_source_hashes':{s['source_id']:s.get('sha256') for s in packet.get('sources',[])},
                    'reviewed_content_sha256':content_fingerprint(root,packet),
                    'notice':'Read-only snapshot. Reviewer must inspect this exact version; copying the token proves no reading.'}
        elif args.command=="merge":
            result=merge_handoff(root,read(args.file))
        elif args.command=="ingest-review":
            result=ingest_review(root,read(args.file))
        elif args.command=="repair-ready":
            result=repair_ready(root,args.id,args.evidence)
        else:
            packet,state=read(root/"paper_packet.json"),read(root/"execution_state.json")
            sync_inventory(root,packet,state)
            result=commit(root,packet,state,"Synced canonical inventory/state without granting acceptance.")
        print(json.dumps(result,ensure_ascii=True,indent=2))
        return 0
    except (RunError,OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
        print(json.dumps({"error_code":getattr(exc,"code","RECORD_ERROR"),"message":str(exc),
                          "terminal_decision":"CONTINUE","may_send_final":False},ensure_ascii=True,indent=2))
        return 1


if __name__=="__main__":
    raise SystemExit(main())

