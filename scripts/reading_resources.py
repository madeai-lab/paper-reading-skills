"""Resource ledger for adaptive reading: measured helper work and host-reported usage, never estimates."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from reading_run_records import RunError

LEDGER = 'resource_log.jsonl'
HELPER_KINDS = {'IMPORT', 'PDF_EXTRACTION', 'EXTRACTION_REUSED', 'OUTLINE', 'PAGE_READ', 'TEXT_SEARCH', 'CROP'}
HOST_KINDS = {'MODEL_CALL', 'REVIEWER_CALL'}
DEPTHS = {'L0', 'L1', 'L2', 'L3'}
BUDGET = {'L0': (3, 2000), 'L1': (8, 6000), 'L2': (20, 20000), 'L3': (40, 40000),
          'FIRST_REVIEW': (20, 20000), 'DELTA_REVIEW': (8, 8000)}


def _append(root, entry):
    path = Path(root)/LEDGER
    with path.open('a', encoding='utf8', newline='\n') as stream:
        stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + '\n')
    return entry


def record(root, kind, paper_id=None, *, duration_s=None, **fields):
    """Append helper work this process actually performed."""
    if kind not in HELPER_KINDS:
        raise RunError('INVALID_ARGUMENT', 'Unknown helper resource kind.')
    return _append(root, {'at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'kind': kind,
                          'origin': 'HELPER_MEASURED', 'paper_id': paper_id,
                          'duration_s': None if duration_s is None else round(duration_s, 4), **fields})


@contextmanager
def timed(root, kind, paper_id=None, **fields):
    """Measure one helper call with a monotonic clock; a failed call is not logged as work done."""
    started = time.perf_counter()
    extra = {}
    yield extra
    record(root, kind, paper_id, duration_s=time.perf_counter() - started, **fields, **extra)


def log_usage(root, kind, paper_id, depth, *, tokens_in=None, tokens_out=None, duration_s=None,
              measured_by=None, note=None, review_round=None, phase=None, task_kind=None):
    """Record a model or reviewer call the host actually made. Quantities need a stated measurement source."""
    if kind not in HOST_KINDS or depth not in DEPTHS:
        raise RunError('INVALID_ARGUMENT', 'Use kind MODEL_CALL or REVIEWER_CALL and the depth the call served.')
    if review_round is not None and (kind != 'REVIEWER_CALL' or type(review_round) is not int or review_round < 1):
        raise RunError('INVALID_ARGUMENT', 'review_round is a positive integer for reviewer usage only.')
    numbers = [tokens_in, tokens_out, duration_s]
    if any(n is not None and (type(n) not in (int, float) or n < 0) for n in numbers):
        raise RunError('INVALID_ARGUMENT', 'Usage quantities are non-negative numbers.')
    if any(n is not None for n in numbers) and not (isinstance(measured_by, str) and measured_by.strip()):
        raise RunError('USAGE_SOURCE_REQUIRED', 'State where the tokens or duration were measured (--measured-by). '
                       'Leave them out when the runtime does not report them; never estimate.')
    return _append(root, {'at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'kind': kind,
                          'origin': 'HOST_REPORTED', 'paper_id': paper_id, 'depth': depth,
                          'task_kind': task_kind or 'PAPER_READING', 'role': 'REVIEWER' if kind == 'REVIEWER_CALL' else 'OWNER',
                          'phase': phase or depth, 'review_round': review_round,
                          'tokens_in': tokens_in, 'tokens_out': tokens_out, 'duration_s': duration_s,
                          'measured_by': measured_by.strip() if measured_by else None, 'note': note})


def entries(root):
    path = Path(root)/LEDGER
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf8').splitlines() if line.strip()]


def _total(rows, key):
    values = [row[key] for row in rows if row.get(key) is not None]
    return (round(sum(values), 4) if values else None), len(values)


def budget_windows(host):
    # Group by paper and task, never by depth for reader totals. A workspace is one task.
    groups = {}
    for event in host:
        reviewer = event['kind'] == 'REVIEWER_CALL'
        rnd = event.get('review_round') if reviewer else None
        key = (event['paper_id'], event.get('task_kind') or 'PAPER_READING', reviewer, rnd)
        groups.setdefault(key, []).append(event)
    result = []
    for (pid, task, reviewer, rnd), events in groups.items():
        depth = max(e['depth'] for e in events)
        window = ('FIRST_REVIEW' if rnd == 1 else 'DELTA_REVIEW' if rnd else None) if reviewer else depth
        # L2 claim review has no calibrated reviewer threshold.
        limits = BUDGET.get(window) if not reviewer or depth == 'L3' else None
        output, measured = _total(events, 'tokens_out')
        result.append({'paper_id': pid, 'task_kind': task, 'role': 'REVIEWER' if reviewer else 'OWNER',
                       'depth': depth, 'review_round': rnd, 'responses_reported': len(events),
                       'output_reported': output, 'responses_with_output': measured,
                       'soft_alert': None if not limits else (len(events) >= limits[0] or (output or 0) >= limits[1]) or
                       (None if measured < len(events) else False)})
    return result


def summary(root, paper_id=None):
    rows = [row for row in entries(root) if paper_id is None or row.get('paper_id') == paper_id]
    by_kind = {}
    for row in rows:
        by_kind[row['kind']] = by_kind.get(row['kind'], 0) + 1
    reads, repeated = {}, 0
    for row in rows:
        if row['kind'] != 'PAGE_READ':
            continue
        for page in row.get('pages', []):
            key = (row.get('paper_id'), row.get('source_sha256'), page, row.get('view'), json.dumps(row.get('bbox')))
            reads[key] = reads.get(key, 0) + 1
            repeated += reads[key] > 1
    host = [row for row in rows if row['origin'] == 'HOST_REPORTED']
    calls = {kind: {} for kind in HOST_KINDS}
    for row in host:
        calls[row['kind']][row['depth']] = calls[row['kind']].get(row['depth'], 0) + 1
    tokens_in, with_in = _total(host, 'tokens_in')
    tokens_out, with_out = _total(host, 'tokens_out')
    host_duration, _ = _total(host, 'duration_s')
    helper_duration, _ = _total([row for row in rows if row['origin'] == 'HELPER_MEASURED'], 'duration_s')
    unavailable = []
    if not host:
        unavailable.append('model and reviewer calls: none were reported by the host; this is not a count of zero')
    if tokens_in is None and tokens_out is None:
        unavailable.append('token usage: not provided by the runtime')
    elif with_in < len(host) or with_out < len(host):
        unavailable.append('token usage: reported for only part of the calls; totals are partial')
    if host and host_duration is None:
        unavailable.append('model/reviewer duration: not measured')
    reviewer = calls['REVIEWER_CALL']
    return {'scope': paper_id or 'CORPUS', 'entries': len(rows), 'budget_windows': budget_windows(host), 'by_kind': dict(sorted(by_kind.items())),
            'pdf_extraction_calls': by_kind.get('PDF_EXTRACTION', 0),
            'extractions_reused': by_kind.get('EXTRACTION_REUSED', 0),
            'pages_extracted': sum(row.get('page_count') or 0 for row in rows if row['kind'] == 'PDF_EXTRACTION'),
            'page_reads': {'calls': by_kind.get('PAGE_READ', 0), 'distinct_page_views': len(reads),
                           'repeated_page_reads': repeated},
            'reported_model_calls': {'total': sum(calls['MODEL_CALL'].values()), 'by_depth': dict(sorted(calls['MODEL_CALL'].items()))} if host else None,
            'reported_reviewer_calls': {'total': sum(reviewer.values()), 'by_depth': dict(sorted(reviewer.items())),
                                        'below_L3': sum(n for depth, n in reviewer.items() if depth != 'L3')} if host else None,
            'tokens': {'input': tokens_in, 'output': tokens_out, 'calls_with_input_count': with_in,
                       'calls_with_output_count': with_out, 'reported_calls': len(host)},
            'helper_duration_s': helper_duration, 'host_reported_duration_s': host_duration,
            'unavailable': unavailable,
            'notice': 'Helper entries are measured by these scripts. Model, reviewer and token figures exist only when the '
                      'host reported them with a measurement source. No saving is implied without a controlled comparison.'}
