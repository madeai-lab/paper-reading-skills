"""Canonical paper-reading handoffs and terminal assessment; no model launcher."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

from reading_run_records import (RunError, read, write, digest, evidence, content_fingerprint,
                                 review_content_matches, generated_target, render, MARKER)
from reading_run_check import inspect_run, VERIFIED
from reading_review_contracts import visual_review_errors, structure_errors, visual_fingerprint
import reading_repair_sync as repair_sync
from reading_review_modes import (review_mode, review_plan, coverage_errors, continuation_errors,
                                  review_baseline, review_delta)
from reading_element_contracts import checked_acquisition, element_errors, native_unit_errors, structured_ready
from reading_data_sources import extensions_enabled, is_data_source

from reading_report_quality import quality_errors

REVISION = "2.10"
VISUAL = {"FIGURE", "PANEL", "TABLE", "OTHER_VISUAL"}
STATES = {"INVENTORIED", "READ", "UNDERSTOOD", "CHECKED", "BLOCKED", "NON_INFORMATIVE", "OUT_OF_SCOPE"}
EXPERIMENT_FIELDS = set("experiment_id purpose unit_refs design data_and_sampling split ground_truth models_and_tools comparators budget metrics results uncertainty negative_results failure_cases limitations claim_refs".split())
STATE_FIELDS = set("owner_id writer_ids stage paper_status scope_revision open_unit_ids next_actions blockers stop_reason restart_action history".split())
PLACEHOLDERS = {"see figure", "understood", "correct",
                "see full_notebook.md; granular evidence still being developed."}


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


def current_review(root, packet, review, acquisition=None):
    hashes = {s["source_id"]:s.get("sha256") for s in packet.get("sources", [])}
    return (review.get("reviewed_scope_revision") == packet.get("scope_revision")
            and review.get("reviewed_source_hashes") == hashes
            and review_content_matches(root, packet, review)
            and not visual_review_errors(root, packet, review, acquisition=acquisition)
            and not coverage_errors(root, packet, review, acquisition=acquisition)
            and not quality_errors(root, packet, review))


def continue_with(kind, ids=None, **kwargs):
    return {"terminal_decision":"CONTINUE", "may_send_final":False, "paper_accepted":False,
            "next_action":{"kind":kind, "unit_ids":ids or [], **kwargs},
            "notice":"Perform the next action. This tool cannot intercept a host final message or prove understanding."}


def preflight(root, *, packet=None, acquisition=None):
    """Read-only Owner checks, deliberately excluding pending independent acceptance."""
    if packet is None:
        packet = read(root/'paper_packet.json')
    errors = []
    def error(code, item, message):
        errors.append({'code': code, 'item': item, 'next_action': message})
    try:
        plan = review_plan(packet)
    except (ValueError, KeyError, TypeError) as exc:
        plan = None
        error('REVIEW_PLAN_INVALID', 'review_mode', str(exc))
    task = read(root/'task.json', {})
    if task.get('review_mode') is not None and task['review_mode'] != packet.get('review_mode'):
        error('REVIEW_MODE_MISMATCH', 'task', 'Use the initialized mode; escalation updates task and packet together.')
    try:
        errors.extend(inspect_run(root, require_review=False, acquisition=acquisition))
        for name in render(root, copy.deepcopy(packet), check_only=True):
            error('GENERATED_OUTPUT_STALE', name, 'Regenerate once from canonical records before review.')
        # Decode all current text before a reviewer spends time on a broken snapshot.
        repair_sync.current_documents(root, packet)
        content_fingerprint(root, packet)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        error('PREFLIGHT_RECORD_UNREADABLE', 'current_artifacts', str(exc))
    if not packet.get('claims'):
        error('CLAIMS_MISSING', 'claims', 'Record every report, target and synthesis conclusion as a claim.')
    for claim in packet.get('claims', []):
        if not claim.get('supporting_units') and not (claim.get('allowed_use') == 'HOLD' and claim.get('source_refs')):
            error('CLAIM_EVIDENCE_MISSING', claim.get('claim_id'), 'Link source units or explicitly HOLD the unsupported claim with source context.')
    if packet.get('research_target'):
        target = packet['research_target']
        try:
            validate_target(target)
            analysis = read(root/packet.get('deliverables', {}).get('target_analysis', 'target_analysis.json'))
            if (analysis.get('target_id') != target['target_id'] or analysis.get('target_revision') != target['revision']
                    or {x['question_id'] for x in analysis.get('answers', [])} != {q['id'] for q in target['questions']}):
                raise ValueError('Complete every current target answer before review.')
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            error('TARGET_ANALYSIS_INCOMPLETE', 'target_analysis', str(exc))
    state = read(root/'execution_state.json', {})
    if any(value.get('count', 0) >= 2 for value in state.get('workflow_failures', {}).values()):
        error('WORKFLOW_DIAGNOSIS_REQUIRED', 'workflow', 'Repair recurring generation/synchronization failures before another review.')
    return {'ready_for_review': not errors, 'review_plan': plan, 'errors': errors,
            'semantic_verification_automated': False}


def _data_routes(packet, batch):
    sources = {s['source_id']: s for s in packet.get('sources', []) if is_data_source(s)}
    routes = []
    for u in batch:
        src = sources.get(u.get('source_id'))
        if not src:
            continue
        args = ['read-data', '<run>', '--source-id', src['source_id']]
        locators = u.get('locators') or []
        loc = locators[0] if locators and isinstance(locators[0], dict) else {}
        for key, flag in [('sheet','--sheet'), ('rows','--rows'), ('header_row','--header-row'),
                          ('fields','--fields'), ('json_pointer','--json-pointer'), ('lines','--lines')]:
            if key in loc and (loc[key] is not None or key == 'header_row'):
                values = loc[key] if isinstance(loc[key], list) else [loc[key]]
                if key == 'header_row' and values == [None]:
                    values = [0]
                args.extend([flag, *map(str, values)])
        routes.append({'unit_id':u['unit_id'], 'source_id':src['source_id'], 'format':src.get('format'),
                       'first_read_argv':args, 'locator_count':len(locators)})
    return routes


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
        and progress[r['repair_id']].get('scope_revision') == packet.get('scope_revision')
        and repair_sync.progress_current(root, packet, state, r, latest.get('review_id')))] if latest and latest.get('decision') in {'REVISION_REQUIRED','MATERIAL_BLOCKED'} else []
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
    acquisition = checked_acquisition(root, packet)
    acquisition_errors = element_errors(root, packet, acquisition=acquisition)
    if acquisition_errors:
        if acquisition_errors[0]['code'] == 'ELEMENTS_APPEND_REQUIRED':
            return continue_with('EXTRACT_ELEMENTS', errors=acquisition_errors, append=True,
                                 instruction='Run extract-elements --append for the newly registered sources. '
                                             'Earlier pages are immutable. A data-file-only append needs no pdfplumber.')
        return continue_with('EXTRACT_ELEMENTS', errors=acquisition_errors,
                             instruction='For the first extraction use a provisioned pdfplumber interpreter. '
                                         'If extraction exists, inspect the reported source or manifest error instead; '
                                         'do not overwrite evidence, install software, use OCR or migrate a frozen run.')
    if latest and latest.get("decision") in {"REVISION_REQUIRED","MATERIAL_BLOCKED"}:
        if accessible_repairs:
            batch = accessible_repairs[:3]
            ids = list(dict.fromkeys(uid for item in batch for uid in item["unit_ids"]))
            return continue_with("REPAIR",ids, repair_ids=[r["repair_id"] for r in batch], requests=batch,
                                 instruction="Inspect source and repair affected records/dependencies; save repair evidence and obtain reviewer reinspection.")
    if packet.get("gate_results",{}).get("G0",{}).get("decision") != "PASS":
        instruction = ('Start with outline (optional --out tools/inventory.draft.json), not a full page dump. '
                       'For PDFs verify heading boundaries, columns and panels with section-coverage --details after sync. '
                       'For DATA_FILE sources inventory actual rows/fields, pointers or lines using read-data. '
                       'Only the Owner can merge an evidenced G0.' if packet.get('content_acquisition') else
                       'Inspect the original source identity and scope, inventory all units and merge an evidenced G0.')
        return continue_with("SOURCE_INVENTORY", instruction=instruction)
    if accessible:
        batch = accessible[:4]
        routes = _data_routes(packet, batch)
        instructions = []
        if routes:
            instructions.append('Use read-data with the registered locators for each DATA_FILE unit. first_read_argv starts at the first locator; inspect the others too. A structure view is navigation only.')
        if len(routes) < len(batch):
            instructions.append('Read mapped PDF prose with read-section --id ID --format text and follow next_cursor; for native visuals use read-elements --view locator, then render-crop and open the PNG. Use original sources for unmapped/legacy units.')
        instructions.append('Submit source-specific explanations, not flags.')
        return continue_with('READ_AND_RECORD_UNITS', [u['unit_id'] for u in batch], units=batch,
                             open_unit_count=len(units), instruction=' '.join(instructions),
                             **({'data_reads':routes} if routes else {}))
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
    if packet.get('research_target'):
        target = packet['research_target']
        validate_target(target)
        path = packet.get('deliverables', {}).get('target_analysis', 'target_analysis.json')
        try:
            analysis = read(root/path, {})
            answered = {row['question_id'] for row in analysis.get('answers', [])}
            matches = (analysis.get('target_id') == target['target_id']
                       and analysis.get('target_revision') == target['revision']
                       and answered == {q['id'] for q in target['questions']})
        except (ValueError, TypeError, KeyError, AttributeError):
            matches = False
        if not matches:
            return continue_with('WRITE_TARGET_ANALYSIS', path=path,
                                 instruction='Answer every current target question from checked evidence; retain unsupported questions and limitations. Then obtain actual review.')
    if not latest or latest.get("decision") not in VERIFIED or not current_review(root,packet,latest,acquisition=acquisition):
        if 'review_mode' in packet:
            checked = preflight(root, packet=packet, acquisition=acquisition)
            if not checked['ready_for_review']:
                return continue_with('PREFLIGHT_REVIEW', errors=checked['errors'],
                                     instruction='Fix Owner-controlled defects together before spending independent review.')
        return continue_with("REQUEST_REVIEW", review_plan=review_plan(packet),
                             instruction="Use the distinct source-first reviewer for this mode; reuse the same actual session for delta review. Ingest its actual decision.")
    visual_errors = visual_review_errors(root, packet, latest, acquisition=acquisition)
    if visual_errors:
        return continue_with('REQUEST_REVIEW', errors=visual_errors,
                             instruction='Obtain actual direct visual review; blocked image access is not acceptance.')
    errors = inspect_run(root, acquisition=acquisition)
    if errors:
        return continue_with("REPAIR_RECORDS",errors=errors[:6],error_count=len(errors),
                             instruction="Repair actual work or specific inconsistent records, then assess again.")
    if state.get("open_unit_ids") or state.get("paper_status") != packet.get("paper_status"):
        return continue_with("SYNC_STATE",instruction="Sync canonical state from current evidence without changing review decisions.")
    return {"terminal_decision":"ACCEPTED", "may_send_final":True, "paper_accepted":True,
            "review_mode": review_mode(packet), "coverage_label": review_plan(packet)['coverage_label'],
            "next_action":{"kind":"FINAL_DELIVERY","unit_ids":[]},
            "notice":"Recorded independent acceptance and structural consistency, not automated scientific certification."}


def _source_changes(before, after):
    by_id = {s['source_id']: s for s in before}
    current = {s['source_id']: s for s in after}
    changed = set(by_id) ^ set(current)
    reread = set(changed)
    for sid in by_id.keys() & current.keys():
        old, new = by_id[sid], current[sid]
        if (any(old.get(k) != new.get(k) for k in ('sha256', 'format', 'encoding', 'local_path', 'access_state'))
                or old.get('source_kind', 'PDF') != new.get('source_kind', 'PDF')):
            reread.add(sid)
        if any(old.get(k) != new.get(k) for k in ('required_for_scope', 'supplement_of', 'version', 'provenance')):
            changed.add(sid)
    return changed | reread, reread


def _reopen_scope(packet, state, previous_revision, source_ids):
    gates = packet.get('gate_results', {})
    passed = {k: copy.deepcopy(v) for k, v in gates.items() if v.get('decision') == 'PASS'}
    if passed:
        state.setdefault('scope_gate_history', []).append({'scope_revision': previous_revision,
                     'changed_sources': sorted(source_ids), 'gate_results': passed})
        for k in passed:
            gates[k] = {'decision': 'PENDING', 'evidence_refs': [], 'open_items': ['Check the current source scope.']}
        state['stage'] = '01'
    if packet.get('paper_status') in VERIFIED:
        packet['paper_status'] = 'IN_PROGRESS'
        state.setdefault('review_plan', {})['status'] = 'PENDING'


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
    state["inventory_ids"], state["inventory_fingerprint"] = ids, fingerprint
    old_sources = packet.get('sources', [])
    sources = read(root/'01_sources.json') if (root/'01_sources.json').exists() else old_sources
    if extensions_enabled(packet):
        scope_sources, changed_sources = _source_changes(old_sources, sources)
    else:
        # Legacy runs used hashes of previously registered sources for invalidation.
        new_hashes = {s['source_id']:s.get('sha256') for s in sources}
        changed_sources = {s['source_id'] for s in old_sources if s.get('sha256') != new_hashes.get(s['source_id'])}
        scope_sources = changed_sources
    if inventory_changed or scope_sources:
        prior_revision = packet.get('scope_revision',1)
        packet['scope_revision'] = prior_revision + 1
        state['history'].append('Scope revision %s: inventory/source binding changed; recheck dependent evidence.' % packet['scope_revision'])
        if extensions_enabled(packet):
            _reopen_scope(packet, state, prior_revision, scope_sources)
            previous = {s['source_id']:s for s in old_sources}
            for source in sources:
                prior = previous.get(source['source_id'])
                if prior and is_data_source(source) and prior.get('encoding') != source.get('encoding'):
                    state['history'].append(f"Declared encoding for {source['source_id']}: "
                                            f"{prior.get('encoding') or '(default)'} -> {source.get('encoding') or '(default)'}.")
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
        elif changed and prior is not None:
            if extensions_enabled(packet) and prior.get('source_id') in changed_sources:
                unit['read_state'] = 'INVENTORIED'
                unit.pop('content_reading', None)
            else:
                unit['read_state'] = 'READ'
            unit.setdefault("visual_review",{})["actually_viewed"] = False
        merged.append(unit)
    packet["units"] = merged
    packet["sources"] = sources


def commit(root, packet, state, event):
    state.update({"skill_revision":packet.get('skill_revision', state.get('skill_revision', REVISION)),"scope_revision":packet["scope_revision"],
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


def validate_target(target):
    def text(value):
        return isinstance(value, str) and bool(value.strip())

    if target is None:
        return
    if not isinstance(target, dict):
        raise RunError('INVALID_TARGET', 'Research target must be an object or null.')
    required = {'schema_version', 'target_id', 'revision', 'purpose', 'questions',
                'comparison_dimensions', 'hypotheses_to_test', 'output_preferences'}
    valid = (required == target.keys() and type(target.get('schema_version')) is int and target.get('schema_version') == 1
             and text(target.get('target_id')) and text(target.get('purpose'))
             and type(target.get('revision')) is int and target['revision'] > 0)
    if not valid:
        raise RunError('INVALID_TARGET', 'Use the versioned research-target contract.')
    questions = target['questions']
    if (not isinstance(questions, list) or not questions
            or any(not isinstance(q, dict) or not text(q.get('id')) or not text(q.get('text')) for q in questions)
            or len({q['id'] for q in questions}) != len(questions)):
        raise RunError('INVALID_TARGET', 'Questions need unique IDs and nonempty text.')
    for key in ['comparison_dimensions', 'hypotheses_to_test']:
        if not isinstance(target[key], list) or any(not text(x) for x in target[key]):
            raise RunError('INVALID_TARGET', key + ' must be a list of nonempty strings.')
    if not isinstance(target['output_preferences'], dict):
        raise RunError('INVALID_TARGET', 'output_preferences must be an object.')


def set_target(root, target):
    validate_target(target)
    packet, state = read(root/'paper_packet.json'), read(root/'execution_state.json')
    old = packet.get('research_target')
    history = state.get('research_target_history', [])
    if target:
        previous = [entry for entry in history+[old] if entry and entry.get('target_id') == target['target_id']]
        if any(entry != target and target['revision'] <= entry.get('revision', 0) for entry in previous):
            raise RunError('INVALID_TARGET', 'Changed content under the same target_id needs a higher revision, including after clearing the target.')
    if old and old not in history:
        history.append(copy.deepcopy(old))
    state['research_target_history'] = history
    packet['research_target'] = copy.deepcopy(target)
    if target is not None:
        packet['deliverables']['target_analysis'] = 'target_analysis.json'
    else:
        packet['deliverables'].pop('target_analysis', None)
    task = read(root/'task.json', {})
    task['research_target'] = copy.deepcopy(target)
    write(root/'task.json', task)
    return commit(root, packet, state, 'Bound explicit research target; retain source reading, recheck changed analysis/report.')


def initialize(root, source, owner, language, target=None, mode='KEY_CLAIMS'):
    validate_target(target)
    review_mode({'review_mode': mode})
    if root.exists():
        raise RunError("RUN_EXISTS","Choose a new output directory; existing runs are never overwritten.")
    source = source.resolve()
    with source.open("rb") as stream:
        if stream.read(5)!=b"%PDF-":
            raise RunError("INVALID_SOURCE","Input does not have a PDF header.")
    templates = Path(__file__).resolve().parent.parent/"shared"
    packet,state,task = [read(templates/name) for name in ["packet.template.json","execution-state.template.json","task.template.json"]]
    src = {"source_id":"SRC-01","title":None,"version":None,"publication_status":None,
           "source_kind":"PDF","local_path":"source.pdf","sha256":digest(source),"page_count":None,"access_state":"AVAILABLE",
           "required_for_scope":True,"supplement_of":None,"missing_reason":None}
    root.mkdir(parents=True)
    shutil.copyfile(source,root/"source.pdf")
    packet.update({"template_only":False,"skill_revision":REVISION,"task_id":root.name,"paper_id":root.name,
                   "owner_id":owner,"writer_ids":[owner],"paper_status":"IN_PROGRESS","sources":[src],
                   "review_mode":mode})
    packet['review_requirements'] = {'direct_visual_inspection': True, 'repair_dependency_sync': True, 'reader_explanation': True, 'report_presentation': True}
    packet['content_acquisition'] = {'method': 'PDFPLUMBER_NATIVE', 'manifest_ref': 'source_elements/manifest.json'}
    packet["deliverables"] = {k:k+".md" for k in ["full_notebook","report","material_index","user_review","independent_review"]}
    packet["deliverables"]["report_readability"] = "report_readability.json"
    state.update({"template_only":False,"skill_revision":REVISION,"task_id":root.name,"owner_id":owner,
                  "writer_ids":[owner],"stage":"01","paper_status":"IN_PROGRESS","repair_progress":{}})
    task.update({"template_only":False,"skill_revision":REVISION,"task_id":root.name,"paper_id":root.name,
                 "review_mode":mode,
                 "content_acquisition":copy.deepcopy(packet['content_acquisition']),
                 "language":language,"source_files":["source.pdf"],"output_dir":str(root),"source_root":str(root)})
    if target is not None:
        task['research_target'] = copy.deepcopy(target)
        packet['research_target'] = copy.deepcopy(target)
        packet['deliverables']['target_analysis'] = 'target_analysis.json'
    for name,value in [("task.json",task),("assignment_map.json",{"owner":owner,"roles":{},"review_capacity":"PLAN_AT_STARTUP"}),
                       ("01_inventory.json",[]),("01_sources.json",[src])]:
        write(root/name,value)
    return commit(root,packet,state,"Initialized canonical records; source identity/reading still require inspection.")


def merge_handoff(root, payload, dry_run=False):
    if not isinstance(payload, dict):
        raise RunError('INVALID_HANDOFF', 'Handoff must be a JSON object; use handoff-template.')
    for key in ['units', 'methods_taxonomy', 'experiments', 'claims', 'issues']:
        if key in payload and (not isinstance(payload[key], list) or any(not isinstance(x, dict) for x in payload[key])):
            raise RunError('INVALID_HANDOFF', key+' must be an array of objects.')
    if 'gate_results' in payload and (not isinstance(payload['gate_results'], dict)
            or any(not isinstance(x, dict) for x in payload['gate_results'].values())):
        raise RunError('INVALID_HANDOFF', 'gate_results must be an object ({} when unused), not an array.')
    packet,state = read(root/"paper_packet.json"),read(root/"execution_state.json")
    sync_inventory(root,packet,state)
    acquisition = checked_acquisition(root, packet)
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
            if (unit.get("kind") in VISUAL and unit.get("visual_review",{}).get("actually_viewed") is not True
                    and not structured_ready(root, packet, unit, acquisition=acquisition)):
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
    proposed_gates = payload.get('gate_results', {})
    for gate,value in proposed_gates.items():
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
        if value['decision'] == 'PASS' and extensions_enabled(packet):
            if value.get('scope_revision', packet['scope_revision']) != packet['scope_revision']:
                raise RunError('INVALID_HANDOFF', f'{gate}: the evidence belongs to a different scope revision.')
            if gate == 'G0':
                inventoried = {u.get('source_id') for u in packet['units']}
                missing = [s['source_id'] for s in packet['sources'] if s.get('required_for_scope')
                           and s.get('access_state') == 'AVAILABLE' and s['source_id'] not in inventoried]
                if missing:
                    raise RunError('INVALID_HANDOFF', 'Inventory the newly available required sources first: '+', '.join(missing))
            for prerequisite in {'G0': (), 'G1': ('G0',), 'G2': ('G0','G1')}[gate]:
                record = proposed_gates.get(prerequisite,packet['gate_results'].get(prerequisite,{}))
                if record.get('decision') != 'PASS':
                    raise RunError('INVALID_HANDOFF', f'Recheck {prerequisite} for the current scope before passing {gate}.')
            value = {**value, 'scope_revision':packet['scope_revision']}
        packet["gate_results"][gate] = copy.deepcopy(value)
    if writer not in packet["writer_ids"]:
        packet["writer_ids"].append(writer)
    defects = structure_errors(packet) + element_errors(root, packet, acquisition=acquisition) + native_unit_errors(root, packet, acquisition=acquisition)
    if defects:
        raise RunError('INVALID_HANDOFF', json.dumps(defects, ensure_ascii=True))
    if dry_run:
        return {'valid': True, 'writer_id': writer, 'notice': 'Read-only shape/reference validation; no files written and no semantic verification.'}
    payload_hash = hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode("utf8")).hexdigest()
    write(root/"handoffs"/(payload_hash+".json"),payload)
    return commit(root,packet,state,"Merged actual handoff from "+writer+"; read states were not automatically promoted.")


def ingest_review(root, review):
    packet,state = read(root/"paper_packet.json"),read(root/"execution_state.json")
    if not isinstance(review, dict) or not isinstance(review.get('gate_decisions'), dict):
        raise RunError('INVALID_REVIEW', 'Review and gate_decisions must be objects; use review-template.')
    if (set(review['gate_decisions']) != {'G0','G1','G2','G3'}
            or any(not isinstance(x, str) or x not in {'PASS','FAIL','PENDING'} for x in review['gate_decisions'].values())):
        raise RunError('INVALID_REVIEW', 'All four gate_decisions must be plain PASS/FAIL/PENDING strings.')
    for key in ['checked_unit_ids','checked_claim_ids','findings','repair_requests','unresolved_reading_gaps']:
        if key in review and not isinstance(review[key], list):
            raise RunError('INVALID_REVIEW', key+' must be an array.')
    acquisition = None
    if review.get('decision') in VERIFIED:
        acquisition = checked_acquisition(root, packet)
        if 'review_mode' in packet:
            checked = preflight(root, packet=packet, acquisition=acquisition)
            if not checked['ready_for_review']:
                raise RunError('PREFLIGHT_REQUIRED', json.dumps(checked['errors'], ensure_ascii=True))
        report_defects = quality_errors(root, packet, review)
        if report_defects:
            raise RunError("INVALID_REVIEW_REPORT", json.dumps(report_defects, ensure_ascii=True))
        defects = coverage_errors(root, packet, review, acquisition=acquisition) + continuation_errors(root, packet, review)
        if defects:
            raise RunError('INVALID_REVIEW_COVERAGE', defects[0]['next_action'])
        defects = visual_review_errors(root, packet, review, acquisition=acquisition)
        if defects:
            raise RunError('INVALID_REVIEW_VISUAL', defects[0]['next_action'])
    if (not isinstance(review.get('review_id'),str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',review['review_id'])
            or not review.get("reviewer_id") or review.get("template_only") is True
            or review.get("decision") not in VERIFIED|{"REVISION_REQUIRED","MATERIAL_BLOCKED"}):
        raise RunError("INVALID_REVIEW","Actual reviewer identity, stable review_id and decision are required.")
    if review["reviewer_id"] in packet.get("writer_ids",[]):
        raise RunError("INVALID_REVIEW","Reviewer must be distinct from actual writers.")
    previous = packet.get('reviews', [])[-1] if packet.get('reviews') else {}
    if review['decision'] in VERIFIED and previous.get('decision') in {'REVISION_REQUIRED', 'MATERIAL_BLOCKED'}:
        for request in requests(previous, packet['owner_id']):
            if not repair_sync.progress_current(root, packet, state, request, previous.get('review_id')):
                raise RunError('REPAIR_SYNC_REQUIRED', 'Recheck every current dependency before accepted reinspection: ' + request['repair_id'])
    if review["decision"] in VERIFIED and (not current_review(root,packet,review,acquisition=acquisition) or review.get("repair_requests")
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
    if 'review_mode' in packet:
        baseline = root/'reviews'/(rid+'.baseline.json')
        if not baseline.exists():
            write(baseline, review_baseline(root, packet))
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


def repair_ready(root, repair_id, ref, sync_file=None):
    packet,state = read(root/"paper_packet.json"),read(root/"execution_state.json")
    latest = packet.get("reviews",[])[-1] if packet.get("reviews") else {}
    request = next((r for r in requests(latest,packet['owner_id']) if r['repair_id']==repair_id),None)
    if request is None or not evidence(root,[ref]):
        raise RunError("INVALID_REPAIR","Use a latest-review repair ID and existing repair evidence.")
    sync_record = {}
    if packet.get('review_requirements', {}).get('repair_dependency_sync'):
        if sync_file is None:
            raise RunError('REPAIR_SYNC_REQUIRED', 'Run repair-scan, inspect dependencies and provide --sync-file under repair_sync/.')
        path = Path(sync_file).resolve()
        if not path.is_relative_to((root/'repair_sync').resolve()) or not path.is_file():
            raise RunError('INVALID_REPAIR_SYNC', 'Store the completed synchronization report under this run\'s repair_sync/.')
        try:
            repair_sync.validate(root, packet, request, latest.get('review_id'), read(path))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise RunError('INVALID_REPAIR_SYNC', str(exc)) from exc
        sync_record = {'dependency_sync_ref': path.relative_to(root).as_posix(),
                       'dependency_sync_sha256': digest(path)}
    state.setdefault("repair_progress",{})[repair_id] = {"status":"READY_FOR_REVIEW",
        "scope_revision":packet["scope_revision"],"review_id":latest.get('review_id'),
        "request_sha256":hashlib.sha256(json.dumps(request,sort_keys=True,ensure_ascii=False).encode('utf8')).hexdigest(),
        "evidence_refs":[ref], **sync_record}
    return commit(root,packet,state,"Saved repair evidence for "+repair_id+"; reviewer reinspection is still required.")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["init","merge","ingest-review","repair-scan","repair-ready","sync","next","snapshot","set-target","validate-handoff","handoff-template","review-template",
                                          "review-plan","preflight","review-delta","escalate-review","workflow-failure","workflow-repaired",
                                          "extract-elements","outline","read-elements","read-section","section-coverage","render-crop","read-data"])
    parser.add_argument("run_directory",type=Path)
    parser.add_argument("--source",type=Path)
    parser.add_argument("--target",type=Path, help="Explicit research-target JSON for init.")
    parser.add_argument("--owner",default="root")
    parser.add_argument("--language",choices=["zh-CN","en"],default="zh-CN")
    parser.add_argument('--review-mode', choices=['KEY_CLAIMS', 'FULL_DOUBLE_READ'], default='KEY_CLAIMS')
    parser.add_argument("--file",type=Path)
    parser.add_argument("--id")
    parser.add_argument("--evidence")
    parser.add_argument('--sync-file', type=Path)
    parser.add_argument('--terms', nargs='+')
    parser.add_argument('--obsolete', nargs='+')
    parser.add_argument('--writer')
    parser.add_argument('--units', nargs='+')
    parser.add_argument('--pages', nargs='+', type=int)
    parser.add_argument('--bbox', nargs=4, type=float)
    parser.add_argument('--source-id')
    parser.add_argument('--cursor', help='Resume read-section from its previous next_cursor.')
    parser.add_argument('--max-chars', type=int, default=18000, help='Maximum bounded read (1-18000); omit for the default. Continue long sections with their cursor.')
    parser.add_argument('--format', choices=('text','json'), help='Output for outline (default: text) or read-section (default: json).')
    parser.add_argument('--out', type=Path, help='New run-relative draft under tools/ or crop under evidence/ or reviews/.')
    parser.add_argument('--details', action='store_true', help='Show unmapped native word runs in the coverage audit.')
    parser.add_argument('--offset', type=int, help='Resume section-coverage --details with the same page filter.')
    parser.add_argument('--scale', type=float, help='Crop pixels per PDF point (default: 2).')
    parser.add_argument('--view', choices=('detail', 'locator', 'text'),
                        help='read-elements only: native detail (default), object locators, or plain text for spot checks.')
    parser.add_argument('--append', action='store_true',
                        help='extract-elements only: bind newly registered sources into an existing 2.10+ extraction.')
    parser.add_argument('--sheet', help='read-data only: XLSX worksheet name.')
    parser.add_argument('--rows', nargs=2, type=int, help='read-data only: first and last table row (1-based, inclusive).')
    parser.add_argument('--header-row', type=int, help='read-data only: header row (default 1; 0 means no header).')
    parser.add_argument('--fields', nargs='+', help='read-data only: exact header names to select.')
    parser.add_argument('--chars', nargs=2, type=int, help='read-data only: inclusive 1-based character range in one selected text value.')
    parser.add_argument('--json-pointer', help='read-data only: RFC 6901 pointer into a JSON file.')
    parser.add_argument('--lines', nargs=2, type=int, help='read-data only: first and last Markdown/text line.')
    args=parser.parse_args()
    if args.append and args.command != 'extract-elements':
        parser.error('--append applies only to extract-elements')
    data_options = [args.sheet, args.rows, args.header_row, args.fields, args.json_pointer, args.lines, args.chars]
    if args.command != 'read-data' and any(x is not None for x in data_options):
        parser.error('--sheet/--rows/--header-row/--fields/--json-pointer/--lines/--chars apply only to read-data')
    if args.command == 'read-data' and (args.pages or args.bbox or not args.source_id):
        parser.error('read-data needs --source-id and file locators, not PDF pages or a bbox')
    if args.view and args.command != 'read-elements':
        parser.error('--view applies only to read-elements')
    if args.cursor is not None and args.command != 'read-section':
        parser.error('--cursor applies only to read-section')
    if args.command == 'read-section' and (args.pages or args.bbox):
        parser.error('Select a section by --id; use read-elements for a physical region.')
    if args.command == 'section-coverage' and (args.bbox or (args.pages and not args.details)):
        parser.error('Use --pages with --details to filter the coverage diagnostics, not the source audit.')
    if args.command == 'outline' and (args.pages or args.bbox):
        parser.error('outline proposes a map of the source; use read-elements --view text for a page or region')
    if (args.details and args.command != 'section-coverage') or (args.offset is not None and not args.details):
        parser.error('--details and its optional --offset apply only to section-coverage')
    if args.format and args.command not in ('outline','read-section'):
        parser.error('--format applies to outline or read-section; for a page text check use read-elements --view text')
    if args.out is not None and args.command not in ('outline','render-crop'):
        parser.error('--out applies only to outline or render-crop')
    if args.scale is not None and args.command != 'render-crop':
        parser.error('--scale applies only to render-crop')
    if args.command == 'read-section' and args.source_id:
        parser.error('read-section takes its source from the section unit, not --source-id')
    root=args.run_directory.resolve()
    try:
        if args.command=="init":
            if args.source is None:
                raise RunError("INVALID_ARGUMENT","init needs --source.")
            result=initialize(root,args.source,args.owner,args.language,read(args.target) if args.target else None,args.review_mode)
        elif args.command=='review-plan':
            result=review_plan(read(root/'paper_packet.json'))
        elif args.command=='extract-elements':
            from reading_pdf_elements import extract_elements
            result=extract_elements(root, append=args.append)
        elif args.command=='outline':
            from reading_outline import run_outline, outline_text, outline_json
            outline, units, warnings = run_outline(root,args.source_id,args.out)
            if args.format == 'json':
                result = outline_json(outline)
                if units is not None:
                    result.update(draft_path=str(args.out), draft_units=len(units), review=warnings)
            else:
                result = outline_text(outline,units,warnings,args.out)
        elif args.command=='render-crop':
            from reading_crop import render_crop
            if not args.source_id or not args.pages or len(args.pages)!=1 or not args.bbox or not args.out:
                raise RunError('INVALID_ARGUMENT','render-crop requires --source-id, one --pages value, --bbox x0 top x1 bottom and --out evidence/NAME.png or reviews/NAME.png.')
            result=render_crop(root,args.source_id,args.pages[0],args.bbox,args.out,scale=2.0 if args.scale is None else args.scale)
        elif args.command=='read-elements':
            from reading_pdf_elements import read_elements
            result=read_elements(root,args.pages,args.bbox,args.max_chars,args.source_id,view=args.view or 'detail')
        elif args.command=='read-data':
            from reading_data_sources import read_data
            locator={k:v for k,v in [('sheet',args.sheet),('rows',args.rows),('fields',args.fields),
                                     ('json_pointer',args.json_pointer),('lines',args.lines)] if v is not None}
            if args.header_row is not None:
                locator['header_row']=args.header_row or None
            result=read_data(root,args.source_id,locator or None,args.max_chars,chars=args.chars)
        elif args.command=='read-section':
            from reading_sections import read_section
            result=read_section(root,args.id,args.cursor,args.max_chars,output_format=args.format or 'json')
        elif args.command=='section-coverage':
            from reading_sections import section_coverage
            result=section_coverage(root,args.source_id,details=args.details,pages_filter=args.pages,offset=args.offset or 0)
        elif args.command=='preflight':
            result=preflight(root)
        elif args.command=='review-delta':
            result=review_delta(root,read(root/'paper_packet.json'))
        elif args.command=='escalate-review':
            packet,state=read(root/'paper_packet.json'),read(root/'execution_state.json')
            if packet.get('review_mode') != 'KEY_CLAIMS' or not evidence(root,[args.evidence]):
                raise RunError('INVALID_REVIEW_MODE', 'Escalation needs a new KEY_CLAIMS run and existing evidence explaining systemic risk.')
            packet['review_mode']='FULL_DOUBLE_READ'
            task=read(root/'task.json')
            task['review_mode']='FULL_DOUBLE_READ'
            write(root/'task.json',task)
            result=commit(root,packet,state,'Escalated independent coverage to FULL_DOUBLE_READ: '+args.evidence)
        elif args.command in {'workflow-failure','workflow-repaired'}:
            packet,state=read(root/'paper_packet.json'),read(root/'execution_state.json')
            if not args.id or not evidence(root,[args.evidence]):
                raise RunError('INVALID_ARGUMENT','Supply a stable --id category and existing --evidence note.')
            row=state.setdefault('workflow_failures',{}).setdefault(args.id,{'count':0,'evidence_refs':[]})
            row['count']=row['count']+1 if args.command=='workflow-failure' else 0
            row['evidence_refs'].append(args.evidence)
            result=commit(root,packet,state,args.command+': '+args.id)
        elif args.command=='set-target':
            if args.file is None:
                raise RunError('INVALID_ARGUMENT', 'set-target needs --file (JSON object or null).')
            result=set_target(root,read(args.file))
        elif args.command=='handoff-template':
            packet=read(root/'paper_packet.json')
            ids=args.units or [u['unit_id'] for u in packet.get('units',[])]
            units={u['unit_id']:u for u in packet.get('units',[])}
            if not args.writer:
                raise RunError('INVALID_ARGUMENT', 'Set --writer to the actual reading agent ID.')
            unknown=[uid for uid in ids if uid not in units]
            if unknown:
                raise RunError('INVALID_ARGUMENT', f'Unknown synced unit IDs: {unknown[:6]}. Verify the draft and sync 01_inventory.json first.')
            data_ids={s['source_id'] for s in packet.get('sources', []) if is_data_source(s)}
            records=[]
            for uid in ids:
                u=units[uid]
                item={'unit_id':uid,'read_state':'READ','understanding_note':'','evidence_refs':[]}
                if packet.get('content_acquisition') and not u.get('content_reading'):
                    if u.get('source_id') in data_ids:
                        item['content_reading']={'mode':'DATA_FILE','unresolved_conflicts':[],'conflict_resolution_refs':[]}
                    else:
                        item['content_reading']={'mode':None,'page_refs':[],'element_ids':[],'conflict_resolution_refs':[]}
                if u.get('kind') in VISUAL and u.get('read_state') == 'INVENTORIED':
                    item['visual_review']={'required':True,'actually_viewed':False,'artifact_refs':[],'checks':[],'limitations':[]}
                records.append(item)
            result={'writer_id':args.writer, 'units':records,
                    'methods_taxonomy':[], 'experiments':[], 'claims':[], 'issues':[], 'gate_results':{}}
        elif args.command=='review-template':
            result=read(Path(__file__).resolve().parent.parent/'shared/review-record.template.json')
            result['reviewer_id']=args.writer
            packet=read(root/'paper_packet.json')
            plan=review_plan(packet)
            result.update({'review_mode':plan['review_mode'],'coverage_label':plan['coverage_label']})
            if 'review_mode' in packet:
                result['coverage_check']={'source_structure_checked':False,'owner_coverage_checked':False,
                                          'omissions':[],'evidence_refs':[]}
        elif args.command=='validate-handoff':
            result=merge_handoff(root,read(args.file),dry_run=True)
        elif args.command=="next":
            result=assess(root)
        elif args.command=='snapshot':
            packet=read(root/'paper_packet.json')
            result={'reviewed_scope_revision':packet.get('scope_revision'),
                    'reviewed_source_hashes':{s['source_id']:s.get('sha256') for s in packet.get('sources',[])},
                    'reviewed_content_sha256':content_fingerprint(root,packet),
                    'notice':'Read-only snapshot. Reviewer must inspect this exact version; copying the token proves no reading.'}
            if args.file:
                result['reviewed_visual_evidence_sha256'] = visual_fingerprint(root, read(args.file))
        elif args.command=="merge":
            result=merge_handoff(root,read(args.file))
        elif args.command=="ingest-review":
            result=ingest_review(root,read(args.file))
        elif args.command=='repair-scan':
            packet=read(root/'paper_packet.json')
            latest=packet.get('reviews', [])[-1] if packet.get('reviews') else {}
            request=next((r for r in requests(latest,packet['owner_id']) if r['repair_id']==args.id),None)
            if request is None:
                raise RunError('INVALID_REPAIR','Use an ID from the latest actual failed review.')
            result=repair_sync.scan(root,packet,request,latest.get('review_id'),args.terms,args.obsolete)
        elif args.command=="repair-ready":
            result=repair_ready(root,args.id,args.evidence,args.sync_file)
        else:
            packet,state=read(root/"paper_packet.json"),read(root/"execution_state.json")
            sync_inventory(root,packet,state)
            result=commit(root,packet,state,"Synced canonical inventory/state without granting acceptance.")
        if args.command == 'read-data':
            from reading_data_sources import data_json
            result = data_json(result)
        if isinstance(result,str):
            # Plain output is part of the CLI wire format, independent of the console code page.
            if hasattr(sys.stdout,'buffer'):
                sys.stdout.buffer.write((result+'\n').encode('utf-8'))
            else:
                print(result)
        elif args.command in ('read-elements','read-section','section-coverage','outline'):
            print(json.dumps(result,ensure_ascii=True,separators=(',', ':')))
        else:
            print(json.dumps(result,ensure_ascii=True,indent=2))
        return 0
    except (RunError,OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
        print(json.dumps({"error_code":getattr(exc,"code","RECORD_ERROR"),"message":str(exc),
                          "terminal_decision":"CONTINUE","may_send_final":False},ensure_ascii=True,indent=2))
        return 1


if __name__=="__main__":
    raise SystemExit(main())

