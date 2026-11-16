"""Bind reader-facing explanation checks to the inspected report, not word counts."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

DIMENSIONS = {"problem", "mechanism", "metrics", "experiments", "visuals", "limitations"}
SECTION_ROLES = ['source_scope', 'summary', 'problem', 'approach', 'evidence',
                 'limitations', 'navigation']


def presentation_enabled(packet):
    try:
        revision = tuple(int(x) for x in packet.get('skill_revision', '0').split('.'))
    except (ValueError, AttributeError):
        revision = (0,)
    return revision >= (2, 9) or packet.get('review_requirements', {}).get('report_presentation') is True


def section_roles(packet):
    roles = list(SECTION_ROLES)
    if packet.get('research_target'):
        roles.insert(-1, 'target')
    return roles


def _prose(text):
    """Ignore fenced examples and inline code; never treat filenames as links."""
    lines, fence = [], None
    for line in text.splitlines():
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            lines.append('')
        elif marker:
            fence = marker[1]
            lines.append('')
        else:
            lines.append(line)
    prose = re.sub(r'<!--.*?-->', '', '\n'.join(lines), flags=re.S)
    return re.sub(r'(`+).*?\1', '', prose, flags=re.S)


def presentation_errors(root, packet, data, text, review=None):
    if not presentation_enabled(packet):
        return []
    errors = []
    def error(code, message):
        errors.append({'code': code, 'item': 'report_readability', 'next_action': message})
    roles = section_roles(packet)
    prose = _prose(text)
    rows = data.get('sections')
    navigation_start = None
    try:
        if not isinstance(rows, list) or [r.get('role') for r in rows] != roles:
            raise ValueError('Index the common section roles in order; include target only when explicitly bound.')
        positions = []
        for row in rows:
            heading = row.get('heading')
            if not isinstance(heading, str) or not re.fullmatch(r'#{1,6} +\S.*', heading):
                raise ValueError('Use exact, localized ATX heading lines for section locations.')
            matches = list(re.finditer('^' + re.escape(heading) + '$', prose, flags=re.M))
            if len(matches) != 1:
                raise ValueError('Each indexed heading must occur once outside code: ' + heading)
            positions.append(matches[0].start())
        if positions != sorted(set(positions)):
            raise ValueError('Keep distinct section locations in the common reading order.')
        navigation_start = positions[-1]
    except (ValueError, TypeError, AttributeError) as exc:
        error('REPORT_STRUCTURE_INVALID', str(exc))

    # Portable inline Markdown links/images; angle brackets or URL encoding allow spaces.
    # Reference-style links and raw HTML are not the navigation contract.
    report_ref = packet.get('deliverables', {}).get('report', 'report.md')
    parent = (root / report_ref).resolve().parent
    links = set()
    planned_review = packet.get('deliverables', {}).get('independent_review')
    planned_path = (root / planned_review).resolve() if isinstance(planned_review, str) else None
    for match in re.finditer(r'(!?)\[[^\]\n]*\]\((<[^>\n]+>|[^\s)]+)(?:\s+"[^"\n]*")?\)', prose):
        ref = match[2].strip('<>')
        parsed = urlsplit(ref)
        if parsed.scheme.lower() == 'file' or re.match(r'^[a-zA-Z]:', ref):
            error('REPORT_LINK_INVALID', 'Use a portable in-run local destination: ' + ref)
            continue
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        path = (parent / unquote(parsed.path)).resolve()
        try:
            path.relative_to(root)
            if not path.is_file() and not (review is None and not match[1] and path == planned_path):
                raise ValueError('Missing local target: ' + ref)
            if not match[1] and navigation_start is not None and match.start() > navigation_start:
                links.add(path)
        except ValueError as exc:
            error('REPORT_LINK_INVALID', str(exc))
    required = ['full_notebook', 'material_index', 'user_review', 'independent_review']
    if packet.get('research_target'):
        required.append('target_analysis')
    if packet.get('deliverables', {}).get('report_visuals'):
        required.append('report_visuals')
    for key in required:
        ref = packet.get('deliverables', {}).get(key)
        try:
            if not isinstance(ref, str) or not ref:
                raise ValueError('Register and link the actual ' + key + ' output.')
            path = (root / ref).resolve()
            path.relative_to(root)
            if path not in links or (not path.is_file() and not (review is None and key == 'independent_review')):
                raise ValueError('Link the existing registered output: ' + key + ' -> ' + ref)
        except ValueError as exc:
            error('REPORT_NAVIGATION_INCOMPLETE', str(exc))
    if review is not None:
        checked = review.get('report_readability', {})
        if (checked.get('checked_section_roles') != roles
                or not isinstance(checked.get('presentation_assessment'), str)
                or not checked['presentation_assessment'].strip()):
            error('REPORT_PRESENTATION_REVIEW_INCOMPLETE',
                  'The same actual reviewer must assess explanation depth, target separation and usable navigation.')
    return errors


def enabled(packet):
    try:
        revision = tuple(int(x) for x in packet.get("skill_revision", "0").split("."))
    except (ValueError, AttributeError):
        revision = (0,)
    return (revision >= (2, 8) or packet.get("review_requirements", {}).get("reader_explanation") is True
            or presentation_enabled(packet))


def quality_errors(root, packet, review=None):
    if not enabled(packet):
        return []
    root = Path(root).resolve()
    errors = []

    def error(code, message):
        errors.append({"code": code, "item": "report_readability", "next_action": message})

    def local_file(ref):
        if not isinstance(ref, str) or not ref:
            raise ValueError("A local file reference is required.")
        path = (root / ref).resolve()
        path.relative_to(root)
        if not path.is_file():
            raise ValueError("Missing local file: " + ref)
        return path

    try:
        report = local_file(packet.get("deliverables", {}).get("report"))
        quality = local_file(packet.get("deliverables", {}).get("report_readability"))
        data = json.loads(quality.read_text(encoding="utf-8-sig"))
        text = report.read_text(encoding="utf-8-sig")
        sha = hashlib.sha256(report.read_bytes()).hexdigest()
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("Use the report-readability template schema_version 1.")
        if data.get("template_only") is not False or data.get("report_sha256") != sha:
            error("REPORT_QUALITY_STALE", "Complete the check against the final report bytes before review.")
        checks = data.get("checks")
        if (not isinstance(checks, list) or any(not isinstance(c, dict) for c in checks)
                or len(checks) != len(DIMENSIONS)
                or {c.get("dimension") for c in checks} != DIMENSIONS):
            raise ValueError("Explain all six reader questions once, adapting non-applicable dimensions with reasons.")
        units = {u["unit_id"] for u in packet.get("units", [])}
        for check in checks:
            refs = check.get("unit_refs")
            if (not isinstance(refs, list) or any(not isinstance(x, str) or x not in units for x in refs)):
                raise ValueError("Reader-question source unit references must resolve.")
        experiments = data.get("experiments")
        expected = {e["experiment_id"] for e in packet.get("experiments", [])}
        if (not isinstance(experiments, list) or any(not isinstance(e, dict) for e in experiments)
                or len(experiments) != len(expected)
                or {e.get("experiment_id") for e in experiments} != expected):
            error("REPORT_EXPERIMENTS_INCOMPLETE", "Locate a readable account for every recorded experiment, including negative results.")
            experiments = []
        for item in checks + experiments:
            excerpt = item.get("report_excerpt")
            if not isinstance(excerpt, str) or not excerpt.strip() or excerpt not in text:
                error("REPORT_EXPLANATION_UNLOCATED", "Supply an exact excerpt locating the explanation in the current report.")
            if not isinstance(item.get("assessment"), str) or not item["assessment"].strip():
                error("REPORT_EXPLANATION_UNASSESSED", "State what the reader can understand there, or why the dimension is not applicable.")
        display = data.get("display", {})
        if not isinstance(display, dict) or display.get("status") not in {"INSPECTED", "UNAVAILABLE"}:
            raise ValueError("Record actual display inspection or its demonstrated unavailability.")
        refs = display.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            raise ValueError("Save display inspection evidence or the failed-viewer evidence.")
        for ref in refs:
            local_file(ref)
        if not isinstance(display.get("limitations"), str) or not display["limitations"].strip():
            raise ValueError("Describe display scope and limitations, including any unverified layout.")
        if review is not None:
            checked = review.get("report_readability", {})
            if (not isinstance(checked, dict) or checked.get("decision") != "PASS"
                    or checked.get("report_sha256") != sha
                    or not isinstance(checked.get("assessment"), str) or not checked["assessment"].strip()
                    or not isinstance(checked.get("checked_dimensions"), list)
                    or set(checked["checked_dimensions"]) != DIMENSIONS
                    or not isinstance(checked.get("checked_experiment_ids"), list)
                    or set(checked["checked_experiment_ids"]) != expected):
                error("REPORT_REVIEW_INCOMPLETE", "The actual independent reviewer must assess every reader question and experiment against this report; repair unclear explanations.")
        errors.extend(presentation_errors(root, packet, data, text, review))
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        error("REPORT_QUALITY_INVALID", str(exc))
    return errors
