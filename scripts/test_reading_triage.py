"""Static unit tests for screening records, relevance assessment and routing guardrails.

These exercise record rules on constructed inputs. They do not show that an agent reads,
rates or attributes real papers correctly.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import reading_corpus as store
import reading_promotion as promotion
import reading_triage as triage
from reading_run_records import RunError
from test_reading_pdf_elements import minimal_pdf

TARGET = json.loads((Path(__file__).resolve().parent.parent/'shared'/'research-target.example.json').read_text(encoding='utf8'))
NONE = {name: 'NONE' for name in triage.EXCLUSION_DIMENSIONS}


def statement(text, attribution, items):
    return {'text': text, 'attribution': attribution, 'from_items': list(items)}


def assessment(ref, level='METADATA_ONLY', **ratings):
    values = {name: 'LOW' for name in triage.DIMENSIONS}
    values['evidence_adequacy'] = 'UNKNOWN'
    values.update(ratings)
    related = any(values[name] in {'MEDIUM', 'HIGH'} for name in triage.EXCLUSION_DIMENSIONS)
    return {'dimensions': {name: {'rating': rating, 'basis': name + ' judged from the examined items.',
                                  'evidence_level': 'NOT_ASSESSED' if rating == 'UNKNOWN' else level, 'refs': [ref]}
                           for name, rating in values.items()},
            'uncertainty': {'level': 'MEDIUM', 'missing_information': ['Experimental detail is not in what was examined.']},
            'target_links': [{'question_id': 'Q1', 'relation': 'Describes an organizational mechanism.'}] if related else [],
            'mechanisms_worth_study': ['Coordination protocol between planner and executor'],
            'evidenced_points': [], 'author_stated_only': ['Claims a gain over baselines.'],
            'depth_rationale': 'What was examined supports one routing step.',
            'decision_changers': ['The full-text results table.']}


def decision(kind, by='ROUTER_RULES', refs=('M-ABS',), **extra):
    return {'decision': kind, 'decided_by': by, 'reasons': ['Recorded ratings and their stated basis.'],
            'source_refs': list(refs), 'decision_changers': ['Full-text evidence.'], **extra}


class Workspace(unittest.TestCase):
    """A screening workspace with a bound research target."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.ws = self.base/'ws'
        store.init_corpus(self.ws, 'owner', copy.deepcopy(TARGET))

    def add(self, title='Agent workflows for laboratory automation', **fields):
        return store.add_record(self.ws, {'title': title, 'abstract': 'We describe an agent pipeline.', **fields})['paper_id']

    def record(self, pid):
        return store.load_record(self.ws, pid)

    def pdf(self, extra=b''):
        path = self.base/('paper-%d.pdf' % len(extra))
        path.write_bytes(minimal_pdf() + extra)
        return path

    def attach(self, pid, extra=b''):
        return promotion.attach_source(self.ws, pid, self.pdf(extra))

    def l0(self, pid, paper_type='EMPIRICAL', **ratings):
        return {'writer_id': 'screener', 'paper_id': pid, 'depth': 'L0', 'paper_type': paper_type,
                'examined': [{'item_id': 'M-TITLE', 'kind': 'TITLE', 'label': 'Title', 'read_level': 'READ_IN_FULL', 'source_ref': 'REC-01'},
                             {'item_id': 'M-ABS', 'kind': 'ABSTRACT', 'label': 'Abstract', 'read_level': 'READ_IN_FULL', 'source_ref': 'REC-01'}],
                'not_examined': [{'label': 'Paper body', 'reason': 'Metadata screening does not open the paper.'}],
                'uncertainty_flags': [{'code': 'BODY_NOT_READ', 'detail': 'Results are known only as the abstract states them.'}],
                'screening': {'full_text_read': False, 'potential_value': [
                    statement('The authors state a multi-agent pipeline for lab protocols.', 'AUTHOR_CLAIM', ['M-ABS'])]},
                'assessment': assessment('M-ABS', **ratings)}

    def l1(self, pid, route, paper_type='EMPIRICAL', level='AUTHOR_STATEMENT', **ratings):
        ratings.setdefault('evidence_adequacy', 'MEDIUM')
        return {'writer_id': 'skimmer', 'paper_id': pid, 'depth': 'L1', 'paper_type': paper_type,
                'identity_check': {'state': 'VERIFIED_AGAINST_SOURCE', 'basis': 'Title and authors on page 1 match the record.'},
                'examined': [
                    {'item_id': 'S-ABS', 'kind': 'ABSTRACT', 'label': 'Abstract', 'read_level': 'READ_IN_FULL',
                     'locator': {'physical_page': 1, 'section': 'Abstract'}},
                    {'item_id': 'S-INTRO', 'kind': 'SECTION', 'label': '1 Introduction', 'read_level': 'SKIMMED',
                     'locator': {'physical_page': 1, 'section': '1 Introduction'}},
                    {'item_id': 'S-METHOD', 'kind': 'SECTION', 'label': '3 Method overview', 'read_level': 'SKIMMED',
                     'locator': {'physical_page': 1, 'section': '3 Method'}},
                    {'item_id': 'T-MAIN', 'kind': 'TABLE', 'label': 'Table 2 main results', 'read_level': 'READ_IN_FULL',
                     'locator': {'physical_page': 1, 'object_label': 'Table 2'}}],
                'not_examined': [{'label': '4.2 Ablations', 'reason': 'Outside the skim.'},
                                 {'label': 'Appendix A', 'reason': 'Not opened.'}],
                'uncertainty_flags': [{'code': 'ABLATIONS_NOT_READ', 'detail': 'Module contribution is unknown.'}],
                'card': {'research_problem': statement('How to coordinate planner and executor agents.', 'AUTHOR_CLAIM', ['S-INTRO']),
                         'claimed_contributions': [statement('A two-level coordination protocol.', 'AUTHOR_CLAIM', ['S-ABS', 'S-INTRO'])],
                         'core_method': statement('A planner assigns steps; executors report back.', 'AUTHOR_CLAIM', ['S-METHOD']),
                         'headline_evidence': [statement('Table 2 lists 82% task success against 61% for the baseline.',
                                                         'REPORTED_OBSERVATION', ['T-MAIN'])],
                         'potential_limitations': [statement('One laboratory; ablations not read.', 'ANALYST_INFERENCE', ['S-METHOD'])]},
                'assessment': assessment('S-INTRO', level=level, **ratings),
                'decision': route}

    def l2(self, pid, claims=None):
        claims = claims or [{'claim_id': 'LC1', 'text': 'Executors report failures to the planner, which replans.',
                             'attribution': 'REPORTED_OBSERVATION', 'focus_id': 'F1', 'evidence_state': 'SUPPORTED',
                             'supporting_items': ['S-COORD'], 'conditions': ['Described design; not a measured effect.'],
                             'limits': 'Only section 3.2 was read.'}]
        return {'writer_id': 'reader', 'paper_id': pid, 'depth': 'L2', 'paper_type': 'EMPIRICAL',
                'identity_check': {'state': 'VERIFIED_AGAINST_SOURCE', 'basis': 'Same file as the skim.'},
                'examined': [{'item_id': 'S-COORD', 'kind': 'SECTION', 'label': '3.2 Coordination', 'read_level': 'READ_IN_FULL',
                              'locator': {'physical_page': 1, 'section': '3.2 Coordination'}},
                             {'item_id': 'S-ABL', 'kind': 'SECTION', 'label': '4.2 Ablations', 'read_level': 'SKIMMED',
                              'locator': {'physical_page': 1, 'section': '4.2 Ablations'}}],
                'not_examined': [{'label': 'Sections 5-6 and appendices', 'reason': 'Outside the coordination focus.'}],
                'uncertainty_flags': [],
                'targeted': {'focus': [{'focus_id': 'F1', 'description': 'Coordination mechanism', 'question_ids': ['Q1'],
                                        'items': ['S-COORD']}],
                             'local_claims': claims,
                             'scope_statement': 'Section 3.2 read in full; ablations skimmed; everything else unread.'},
                'assessment': assessment('S-COORD', level='EXAMINED_SOURCE', evidence_adequacy='MEDIUM',
                                         methodological_relevance='MEDIUM', research_utility='MEDIUM')}

    def expect(self, code, function, *args, **kwargs):
        with self.assertRaises(RunError) as context:
            function(*args, **kwargs)
        self.assertEqual(context.exception.code, code, str(context.exception))
        return str(context.exception)

    def skimmed(self, route=None, **ratings):
        """A paper screened at L0, routed to L1 and skimmed."""
        ratings = ratings or {'topic_relevance': 'MEDIUM'}
        self.serial = getattr(self, 'serial', 0) + 1
        pid = self.add('Agent coordination study number %d' % self.serial)
        store.submit(self.ws, {**self.l0(pid, **ratings), 'decision': decision('PROMOTE_TO_L1')})
        self.attach(pid)
        route = route or decision(store_recommendation(self, pid, ratings), refs=('S-INTRO',), focus=['Coordination protocol'])
        store.submit(self.ws, self.l1(pid, route, **ratings))
        return pid


def store_recommendation(case, pid, ratings):
    """What the rules recommend once the skim with these ratings is recorded."""
    probe = case.l1(pid, None, **ratings)
    probe.pop('decision')
    record = copy.deepcopy(case.record(pid))
    sha = record['full_text']['current_sha256']
    record['passes'].append({'pass_id': 'L1-probe', 'depth': 'L1', 'status': 'CURRENT', 'source_sha256': sha,
                             'examined': [], 'not_examined': [], 'uncertainty_flags': [], 'conflicts': []})
    return triage.recommend(record, {'assessment_id': 'probe', **probe['assessment']})['decision']


class ScreeningRuleTests(Workspace):
    def test_unrelated_paper_is_excluded_at_metadata_depth_with_a_recorded_basis(self):
        pid = self.add('Radar retrieval of soil moisture')
        store.submit(self.ws, self.l0(pid, **NONE))
        self.assertEqual(store.recommend(self.ws, pid)['decision'], 'EXCLUDE_FOR_TARGET')
        status = store.route(self.ws, pid, decision('EXCLUDE_FOR_TARGET', refs=('M-ABS', 'assessment:A01')))
        self.assertEqual(status['tier'], 'METADATA_SCREENED')
        self.assertEqual(status['next_action']['kind'], 'NONE')
        self.assertEqual(status['independent_review'], 'NONE')
        saved = self.record(pid)['decisions'][-1]
        self.assertIs(saved['independent_review'], False)
        self.assertEqual(saved['target']['target_id'], TARGET['target_id'])
        self.assertTrue(saved['reasons'] and saved['source_refs'])

    def test_unknown_relevance_is_deferred_never_excluded(self):
        pid = self.add('A title without an abstract')
        store.submit(self.ws, self.l0(pid, **{**NONE, 'topic_relevance': 'UNKNOWN', 'transferability': 'UNKNOWN'}))
        recommended = store.recommend(self.ws, pid)
        self.assertEqual(recommended['decision'], 'DEFER_FOR_EVIDENCE')
        self.assertTrue(recommended['evidence_needed'])
        message = self.expect('EXCLUSION_UNSUPPORTED', store.route, self.ws, pid,
                              decision('EXCLUDE_FOR_TARGET', by='AGENT_JUDGMENT'))
        self.assertIn('topic_relevance', message)
        self.expect('DECISION_BASIS_MISSING', store.route, self.ws, pid, decision('DEFER_FOR_EVIDENCE'))
        store.route(self.ws, pid, decision('DEFER_FOR_EVIDENCE', evidence_needed=['Abstract or full text']))

    def test_relevant_applied_paper_with_low_novelty_is_promoted_not_excluded(self):
        pid = self.add('Deploying tool-using agents in a hospital pharmacy')
        ratings = dict(topic_relevance='HIGH', methodological_relevance='MEDIUM', practical_applicability='HIGH',
                       research_utility='HIGH', novelty_potential='LOW')
        store.submit(self.ws, self.l0(pid, **ratings))
        recommended = store.recommend(self.ws, pid)
        self.assertEqual(recommended['decision'], 'PROMOTE_TO_L1')
        self.assertEqual(recommended['anticipated_depth'], 'L2')
        self.assertTrue(any('NOVELTY_NOT_USED_TO_EXCLUDE' in line for line in recommended['trace']))
        for kind in ['EXCLUDE_FOR_TARGET']:
            self.expect('EXCLUSION_UNSUPPORTED', store.route, self.ws, pid, decision(kind, by='AGENT_JUDGMENT'))

    def test_novelty_alone_never_decides_in_either_direction(self):
        pid = self.add('A novel idea in an unrelated field')
        store.submit(self.ws, self.l0(pid, **{**NONE, 'novelty_potential': 'HIGH'}))
        self.assertEqual(store.recommend(self.ws, pid)['decision'], 'EXCLUDE_FOR_TARGET')

    def test_cross_domain_mechanism_is_routed_to_targeted_reading(self):
        ratings = dict(topic_relevance='LOW', methodological_relevance='MEDIUM', transferability='HIGH', research_utility='MEDIUM')
        pid = self.add('Fleet scheduling for warehouse robots')
        store.submit(self.ws, self.l0(pid, **ratings))
        first = store.recommend(self.ws, pid)
        self.assertEqual((first['decision'], first['anticipated_depth']), ('PROMOTE_TO_L1', 'L2'))
        store.route(self.ws, pid, decision('PROMOTE_TO_L1'))
        self.attach(pid)
        self.expect('FOCUS_REQUIRED', store.submit, self.ws, self.l1(pid, decision('PROMOTE_TO_L2', refs=('S-INTRO',)), **ratings))
        status = store.submit(self.ws, self.l1(pid, decision('PROMOTE_TO_L2', refs=('S-INTRO',),
                                                             focus=['3.2 Coordination protocol']), **ratings))
        self.assertEqual(status['tier'], 'SKIMMED')
        self.assertEqual(status['next_action']['kind'], 'TARGETED_READ_L2')
        self.assertEqual(status['next_action']['focus'], ['3.2 Coordination protocol'])

    def test_survey_and_empirical_papers_follow_different_rules(self):
        self.assertNotEqual(triage.skim_plan('SURVEY')['priority_reading'], triage.skim_plan('EMPIRICAL')['priority_reading'])
        self.assertIn('taxonomy_or_scope', triage.skim_plan('SURVEY')['required_card_fields'])
        self.assertIn('headline_evidence', triage.skim_plan('EMPIRICAL')['required_card_fields'])
        ratings = dict(topic_relevance='HIGH', methodological_relevance='MEDIUM', research_utility='HIGH')
        survey, empirical = self.add('A survey of agent coordination'), self.add('Coordination experiments with agents')
        for pid, kind in [(survey, 'SURVEY'), (empirical, 'EMPIRICAL')]:
            store.submit(self.ws, {**self.l0(pid, paper_type=kind, **ratings), 'decision': decision('PROMOTE_TO_L1')})
            self.attach(pid)
        # A survey has no experiment to report: the card asks for its taxonomy, not for results.
        skim = self.l1(survey, decision('PROMOTE_TO_L2', refs=('S-INTRO',), focus=triage.SURVEY_FOCUS), paper_type='SURVEY', **ratings)
        skim['card']['headline_evidence'] = []
        skim['card']['taxonomy_or_scope'] = statement('Three coordination families by control structure.', 'AUTHOR_CLAIM', ['S-INTRO'])
        self.assertEqual(store.submit(self.ws, skim)['next_action']['kind'], 'TARGETED_READ_L2')
        # Navigation differs by type; neither a survey nor a high-value experiment mandates L3.
        skim = self.l1(empirical, decision('PROMOTE_TO_L2', refs=('S-INTRO',), focus=['Comparison and ablation']), **ratings)
        skim['card']['headline_evidence'] = []
        self.assertEqual(store.submit(self.ws, skim)['next_action']['kind'], 'TARGETED_READ_L2')

    def test_missing_full_text_is_recorded_as_uncertainty(self):
        ratings = dict(topic_relevance='HIGH', research_utility='HIGH')
        pid = self.add()
        store.submit(self.ws, {**self.l0(pid, **ratings), 'decision': decision('PROMOTE_TO_L1')})
        self.assertEqual(store.status(self.ws, pid)['next_action']['kind'], 'ATTACH_FULL_TEXT')
        self.expect('FULL_TEXT_REQUIRED', store.submit, self.ws, self.l1(pid, decision('PROMOTE_TO_L3', refs=('S-INTRO',)), **ratings))
        promotion.mark_unavailable(self.ws, pid, 'Publisher paywall; no open version found.', ['Publisher page', 'arXiv search'])
        recommended = store.recommend(self.ws, pid)
        self.assertEqual((recommended['decision'], recommended['rule']), ('DEFER_FOR_EVIDENCE', 'FULL_TEXT_UNAVAILABLE'))
        self.assertTrue(any('paywall' in need for need in recommended['evidence_needed']))
        self.expect('EXCLUSION_UNSUPPORTED', store.route, self.ws, pid, decision('EXCLUDE_FOR_TARGET', by='AGENT_JUDGMENT'))
        self.assertEqual(store.status(self.ws, pid)['tier'], 'METADATA_SCREENED')

    def test_metadata_screening_cannot_judge_experiments_or_claim_reading(self):
        pid = self.add()
        self.expect('DEPTH_BOUNDARY', store.submit, self.ws, self.l0(pid, evidence_adequacy='HIGH'))
        claimed = self.l0(pid)
        claimed['screening']['full_text_read'] = True
        self.expect('DEPTH_BOUNDARY', store.submit, self.ws, claimed)
        body = self.l0(pid)
        body['examined'].append({'item_id': 'S1', 'kind': 'SECTION', 'label': '4 Results', 'read_level': 'SKIMMED',
                                 'locator': {'physical_page': 4}})
        self.expect('DEPTH_BOUNDARY', store.submit, self.ws, body)
        examined = self.l0(pid)
        examined['assessment']['dimensions']['topic_relevance']['evidence_level'] = 'EXAMINED_SOURCE'
        self.expect('INVALID_ASSESSMENT', store.submit, self.ws, examined)

    def test_explicit_user_depth_request_is_never_downgraded_by_routing(self):
        pid = self.add('Radar retrieval of soil moisture')
        self.expect('USER_INSTRUCTION_REQUIRED', store.request_depth, self.ws, pid, 'L3', ' ')
        store.request_depth(self.ws, pid, 'L3', 'Read this one completely and verify it.')
        store.submit(self.ws, self.l0(pid, **NONE))
        recommended = store.recommend(self.ws, pid)
        self.assertEqual((recommended['decision'], recommended['rule']), ('PROMOTE_TO_L3', 'USER_DEPTH_FLOOR'))
        for kind, extra in [('EXCLUDE_FOR_TARGET', {}), ('BACKGROUND_ONLY', {}), ('PROMOTE_TO_L1', {}),
                            ('DEFER_FOR_EVIDENCE', {'evidence_needed': ['more']})]:
            for by in ['ROUTER_RULES', 'AGENT_JUDGMENT']:
                self.expect('USER_DEPTH_FLOOR', store.route, self.ws, pid, decision(kind, by=by, **extra))
        self.assertEqual(store.status(self.ws, pid)['next_action']['kind'], 'PROMOTE_L3')
        # Only the user can lower the request, and that needs the user's own words.
        self.expect('USER_INSTRUCTION_REQUIRED', store.route, self.ws, pid, decision('EXCLUDE_FOR_TARGET', by='USER'))
        store.route(self.ws, pid, decision('PROMOTE_TO_L3', refs=('M-ABS',)))
        self.assertEqual(self.record(pid)['decisions'][-1]['decided_by'], 'ROUTER_RULES')

    def test_user_can_override_a_routing_suggestion(self):
        pid = self.add('Radar retrieval of soil moisture')
        store.submit(self.ws, {**self.l0(pid, **NONE), 'decision': decision('EXCLUDE_FOR_TARGET')})
        status = store.route(self.ws, pid, {'decision': 'PROMOTE_TO_L2', 'decided_by': 'USER', 'focus': ['Retrieval pipeline'],
                                           'reasons': ['The user wants the pipeline section.'],
                                           'user_instruction': 'Keep it; read the pipeline section closely.'})
        self.assertEqual(status['user_requested_depth'], 'L2')
        self.assertEqual(status['routing']['decided_by'], 'USER')
        self.assertEqual(status['next_action']['kind'], 'ATTACH_FULL_TEXT')

    def test_upgrades_need_a_recorded_decision_or_user_request(self):
        pid = self.add()
        store.submit(self.ws, self.l0(pid, topic_relevance='MEDIUM'))
        self.attach(pid)
        self.expect('UPGRADE_NOT_AUTHORIZED', store.submit, self.ws, self.l1(pid, decision('REMAIN_AT_L1', refs=('S-INTRO',))))
        self.expect('ILLEGAL_TRANSITION', store.route, self.ws, pid, decision('PROMOTE_TO_L3', by='AGENT_JUDGMENT'))
        store.route(self.ws, pid, decision('PROMOTE_TO_L1'))
        status = store.submit(self.ws, self.l1(pid, decision('REMAIN_AT_L1', refs=('S-INTRO',)), topic_relevance='MEDIUM'))
        self.assertEqual(status['tier'], 'SKIMMED')
        history = self.record(pid)['upgrade_history']
        self.assertEqual([(row['from'], row['to']) for row in history], [(None, 'L0'), ('L0', 'L1')])
        self.assertEqual(history[1]['trigger'], {'kind': 'DECISION', 'ref': 'D01'})
        self.assertEqual(history[1]['reused_pass_ids'], ['L0-01'])
        self.assertIs(history[1]['completion_inherited'], False)
        self.expect('DEPTH_REGRESSION', store.submit, self.ws, self.l0(pid))
        self.expect('DEPTH_BOUNDARY', store.submit, self.ws, {**self.l0(pid), 'depth': 'L3'})

    def test_skim_records_what_was_and_was_not_examined(self):
        pid = self.skimmed()
        coverage = store.status(self.ws, pid)['coverage']
        self.assertEqual(coverage['examined_by_kind'], {'ABSTRACT': 2, 'SECTION': 2, 'TABLE': 1, 'TITLE': 1})
        self.assertEqual([row['label'] for row in coverage['not_examined']][-2:], ['4.2 Ablations', 'Appendix A'])
        self.assertIs(coverage['complete_paper_coverage'], False)
        other = self.add('Another paper')
        store.submit(self.ws, {**self.l0(other, topic_relevance='MEDIUM'), 'decision': decision('PROMOTE_TO_L1')})
        self.attach(other)
        skim = self.l1(other, decision('REMAIN_AT_L1', refs=('S-INTRO',)), topic_relevance='MEDIUM')
        skim['not_examined'] = []
        self.expect('COVERAGE_BOUNDARY_MISSING', store.submit, self.ws, skim)
        skim = self.l1(other, decision('REMAIN_AT_L1', refs=('S-INTRO',)), topic_relevance='MEDIUM')
        skim['examined'] = skim['examined'][:1]
        self.expect('DEPTH_BOUNDARY', store.submit, self.ws, skim)
        skim = self.l1(other, None, topic_relevance='MEDIUM')
        self.expect('INVALID_SCREENING_HANDOFF', store.submit, self.ws, skim)

    def test_author_statements_are_not_recorded_as_verified_findings(self):
        pid = self.add()
        store.submit(self.ws, {**self.l0(pid, topic_relevance='MEDIUM'), 'decision': decision('PROMOTE_TO_L1')})
        self.attach(pid)
        route = decision('REMAIN_AT_L1', refs=('S-INTRO',))
        skim = self.l1(pid, route, topic_relevance='MEDIUM')
        skim['card']['headline_evidence'] = [statement('The method reaches 82% success.', 'REPORTED_OBSERVATION', ['S-ABS'])]
        self.assertIn('abstract', self.expect('ATTRIBUTION_UNSUPPORTED', store.submit, self.ws, skim))
        skim = self.l1(pid, route, topic_relevance='MEDIUM')
        skim['card']['headline_evidence'][0]['verification'] = 'VERIFIED'
        self.expect('ATTRIBUTION_UNSUPPORTED', store.submit, self.ws, skim)
        skim = self.l1(pid, route, topic_relevance='MEDIUM')
        skim['examined'][0].update(kind='SECTION')  # an abstract relabelled as body text
        self.expect('INVALID_SCREENING_HANDOFF', store.submit, self.ws, skim)
        skim = self.l1(pid, route, topic_relevance='MEDIUM')
        skim['card']['claimed_contributions'][0]['attribution'] = 'REPORTED_OBSERVATION'
        self.expect('INVALID_SCREENING_HANDOFF', store.submit, self.ws, skim)
        skim = self.l1(pid, route, topic_relevance='MEDIUM')
        skim['card']['core_method']['from_items'] = ['S-NOT-EXAMINED']
        self.expect('UNSUPPORTED_STATEMENT', store.submit, self.ws, skim)
        skim = self.l1(pid, route, topic_relevance='MEDIUM')
        skim['examined'].append({'item_id': 'F-ARCH', 'kind': 'FIGURE', 'label': 'Figure 1 architecture', 'read_level': 'SKIMMED',
                                 'locator': {'physical_page': 1, 'object_label': 'Figure 1'}})
        self.expect('INVALID_SCREENING_HANDOFF', store.submit, self.ws, copy.deepcopy(skim))
        skim['examined'][-1]['caption_only'] = True
        skim['card']['core_method'] = statement('Figure 1 shows a feedback arrow to the planner.', 'REPORTED_OBSERVATION', ['F-ARCH'])
        self.assertIn('caption', self.expect('ATTRIBUTION_UNSUPPORTED', store.submit, self.ws, skim))
        saved = store.submit(self.ws, self.l1(pid, route, topic_relevance='MEDIUM'))
        self.assertEqual(saved['permitted_use']['statements'], 'BOUNDED_BACKGROUND')
        card = triage.latest_pass(self.record(pid), 'L1')['card']
        self.assertEqual({row['verification'] for row in card['headline_evidence']}, {'NOT_VERIFIED'})

    def test_dimensions_stay_separate_and_sourced(self):
        pid = self.add()
        scored = self.l0(pid)
        scored['assessment']['overall_score'] = 0.8
        self.expect('COMPOSITE_SCORE_FORBIDDEN', store.submit, self.ws, scored)
        numeric = self.l0(pid)
        numeric['assessment']['dimensions']['topic_relevance']['rating'] = 4
        self.expect('INVALID_ASSESSMENT', store.submit, self.ws, numeric)
        missing = self.l0(pid)
        del missing['assessment']['dimensions']['transferability']
        self.expect('INVALID_ASSESSMENT', store.submit, self.ws, missing)
        unlinked = self.l0(pid, topic_relevance='HIGH')
        unlinked['assessment']['target_links'] = []
        self.expect('INVALID_ASSESSMENT', store.submit, self.ws, unlinked)
        silent = self.l0(pid, topic_relevance='UNKNOWN')
        silent['assessment']['uncertainty']['missing_information'] = []
        self.expect('INVALID_ASSESSMENT', store.submit, self.ws, silent)
        fixed = self.l0(pid)
        fixed['assessment']['decision_changers'] = []
        self.expect('INVALID_ASSESSMENT', store.submit, self.ws, fixed)
        unassessed = self.l0(pid)
        del unassessed['assessment']
        self.expect('ASSESSMENT_REQUIRED', store.submit, self.ws, unassessed)
        store.submit(self.ws, self.l0(pid))
        saved = self.record(pid)['assessments'][0]
        self.assertEqual(set(saved['dimensions']), set(triage.DIMENSIONS))
        self.assertIs(saved['novelty_externally_checked'], False)
        self.assertNotIn('score', json.dumps(saved).lower())

    def test_screening_records_cannot_carry_gates_reviews_or_acceptance(self):
        pid = self.add()
        for extra in [{'gate_results': {'G3': {'decision': 'PASS'}}}, {'reviewer_id': 'reviewer-2'}]:
            self.expect('INVALID_SCREENING_HANDOFF', store.submit, self.ws, {**self.l0(pid), **extra})
        nested = self.l0(pid)
        nested['screening']['G3'] = 'PASS'
        self.expect('ACCEPTANCE_FIELDS_FORBIDDEN', store.submit, self.ws, nested)
        valued = self.l0(pid)
        valued['uncertainty_flags'] = [{'code': 'STATE', 'detail': 'VERIFIED_FOR_SCOPE'}]
        self.expect('ACCEPTANCE_FIELDS_FORBIDDEN', store.submit, self.ws, valued)
        store.submit(self.ws, self.l0(pid, **NONE))
        self.expect('ACCEPTANCE_FIELDS_FORBIDDEN', store.route, self.ws, pid,
                    {**decision('EXCLUDE_FOR_TARGET'), 'review_id': 'R1'})
        self.assertEqual(self.record(pid)['independent_review'], 'NONE')

    def test_router_rules_label_is_reserved_for_the_rule_output(self):
        pid = self.add()
        store.submit(self.ws, self.l0(pid, topic_relevance='LOW'))
        self.assertEqual(store.recommend(self.ws, pid)['decision'], 'BACKGROUND_ONLY')
        self.expect('INVALID_DECISION', store.route, self.ws, pid, decision('PROMOTE_TO_L1'))
        self.expect('DECISION_BASIS_MISSING', store.route, self.ws, pid, {**decision('PROMOTE_TO_L1', by='AGENT_JUDGMENT'), 'reasons': []})
        self.expect('DECISION_BASIS_MISSING', store.route, self.ws, pid, decision('PROMOTE_TO_L1', by='AGENT_JUDGMENT', refs=()))
        self.expect('DECISION_BASIS_MISSING', store.route, self.ws, pid, decision('PROMOTE_TO_L1', by='AGENT_JUDGMENT', refs=('M-MISSING',)))
        status = store.route(self.ws, pid, decision('PROMOTE_TO_L1', by='AGENT_JUDGMENT'))
        self.assertEqual(self.record(pid)['decisions'][-1]['rule_recommendation'], 'BACKGROUND_ONLY')
        self.assertEqual(status['routing']['decided_by'], 'AGENT_JUDGMENT')


class TargetedReadingTests(Workspace):
    def targeted(self, claims=None):
        pid = self.skimmed(methodological_relevance='MEDIUM', research_utility='MEDIUM')
        return pid, self.l2(pid, claims)

    def test_targeted_reading_judges_only_what_was_read_in_full(self):
        pid, handoff = self.targeted()
        status = store.submit(self.ws, handoff)
        self.assertEqual(status['tier'], 'TARGETED_READ')
        self.assertEqual(status['permitted_use']['local_claims'], {'LC1': 'CANDIDATE_COMPARISON'})
        targeted = triage.latest_pass(self.record(pid), 'L2')['targeted']
        self.assertIs(targeted['complete_paper_verified'], False)
        self.assertIs(targeted['local_claims'][0]['independent_review'], False)
        self.assertEqual(store.recommend(self.ws, pid)['decision'], 'REMAIN_AT_L2')

    def test_weak_missing_and_contradictory_evidence_are_kept_distinct(self):
        pid, handoff = self.targeted()
        base = handoff['targeted']['local_claims'][0]
        skimmed = {**base, 'supporting_items': ['S-ABL']}
        self.assertIn('skimmed', self.expect('UNSUPPORTED_STATEMENT', store.submit, self.ws, self.l2(pid, [skimmed])))
        self.expect('UNSUPPORTED_STATEMENT', store.submit, self.ws, self.l2(pid, [{**base, 'supporting_items': []}]))
        stated = {**base, 'attribution': 'AUTHOR_CLAIM', 'evidence_state': 'UNDETERMINED', 'supporting_items': []}
        self.expect('UNSUPPORTED_STATEMENT', store.submit, self.ws, self.l2(pid, [stated]))
        # An "observation" with nothing observed is not accepted, even when its verdict is left open.
        self.expect('ATTRIBUTION_UNSUPPORTED', store.submit, self.ws, self.l2(pid, [
            {**stated, 'attribution': 'REPORTED_OBSERVATION', 'missing_evidence': ['Any examined result']}]))
        self.expect('UNSUPPORTED_STATEMENT', store.submit, self.ws, self.l2(pid, [{**base, 'evidence_state': 'CONTRADICTED'}]))
        claims = [{**base, 'claim_id': 'LC-WEAK', 'evidence_state': 'LIMITED'},
                  {**base, 'claim_id': 'LC-MISSING', 'attribution': 'AUTHOR_CLAIM', 'evidence_state': 'UNDETERMINED',
                   'supporting_items': [], 'missing_evidence': ['Ablation removing the replanning step']},
                  {**base, 'claim_id': 'LC-CONFLICT', 'evidence_state': 'CONTRADICTED', 'supporting_items': [],
                   'conflicting_items': ['S-COORD']}]
        handoff = self.l2(pid, claims)
        handoff['conflicts'] = [{'conflict_id': 'K1', 'description': 'Abstract says 82%, section 3.2 says 78%.',
                                 'items': ['S-COORD', 'S-ABS'], 'status': 'OPEN'}]
        status = store.submit(self.ws, handoff)
        self.assertEqual(status['permitted_use']['local_claims'],
                         {'LC-WEAK': 'CANDIDATE_COMPARISON', 'LC-MISSING': 'HOLD', 'LC-CONFLICT': 'HOLD'})
        self.assertEqual(status['open_conflicts'], ['K1'])
        # A later pass that checked the passages can close the conflict it inherited.
        handoff = self.l2(pid, claims)
        handoff['conflicts'] = [{'conflict_id': 'K1', 'description': 'Abstract says 82%, section 3.2 says 78%.',
                                 'items': ['S-COORD', 'S-ABS'], 'status': 'EXPLAINED',
                                 'explanation': 'Section 3.2 reports a different warehouse layout than the abstract.'}]
        self.assertEqual(store.submit(self.ws, handoff)['open_conflicts'], [])

    def test_deeper_pass_closes_a_conflict_opened_by_the_skim(self):
        ratings = dict(methodological_relevance='MEDIUM', research_utility='MEDIUM')
        pid = self.add('A paper with a disputed number')
        store.submit(self.ws, {**self.l0(pid, **ratings), 'decision': decision('PROMOTE_TO_L1')})
        self.attach(pid)
        skim = self.l1(pid, decision('PROMOTE_TO_L2', refs=('S-INTRO',), focus=['Resolve K1']), **ratings)
        skim['conflicts'] = [{'conflict_id': 'K1', 'description': 'Abstract and Table 2 disagree.',
                              'items': ['S-ABS', 'T-MAIN'], 'status': 'OPEN'}]
        self.assertEqual(store.submit(self.ws, skim)['open_conflicts'], ['K1'])
        handoff = self.l2(pid)
        handoff['conflicts'] = [{'conflict_id': 'K1', 'description': 'Abstract and Table 2 disagree.', 'items': ['S-COORD', 'T-MAIN'],
                                 'status': 'EXPLAINED', 'explanation': 'The abstract rounds the pooled value; Table 2 lists one layout.'}]
        self.assertEqual(store.submit(self.ws, handoff)['open_conflicts'], [])
        self.assertEqual(store.recommend(self.ws, pid)['decision'], 'REMAIN_AT_L2')

    def test_open_conflicts_and_weak_evidence_change_routing_without_excluding(self):
        ratings = dict(topic_relevance='MEDIUM', evidence_adequacy='LOW')
        pid = self.add()
        store.submit(self.ws, {**self.l0(pid, topic_relevance='MEDIUM'), 'decision': decision('PROMOTE_TO_L1')})
        self.attach(pid)
        skim = self.l1(pid, decision('PROMOTE_TO_L2', refs=('S-INTRO',), focus=['Resolve K1']), **ratings)
        skim['conflicts'] = [{'conflict_id': 'K1', 'description': 'Abstract and Table 2 disagree on the success rate.',
                              'items': ['S-ABS', 'T-MAIN'], 'status': 'OPEN'}]
        status = store.submit(self.ws, skim)
        recommended = store.recommend(self.ws, pid)
        self.assertEqual(recommended['decision'], 'PROMOTE_TO_L2')
        self.assertTrue(any('K1' in line for line in recommended['focus_hint']))
        self.assertTrue(any(line.startswith('WEAK_EVIDENCE') for line in recommended['use_restrictions']))
        self.assertEqual(status['next_action']['kind'], 'TARGETED_READ_L2')

    def test_targeted_reading_needs_a_target_and_a_read_focus(self):
        pid, handoff = self.targeted()
        handoff['targeted']['focus'][0]['question_ids'] = ['Q-UNKNOWN']
        self.expect('INVALID_SCREENING_HANDOFF', store.submit, self.ws, handoff)
        handoff = self.l2(pid)
        handoff['targeted']['focus'][0]['items'] = ['S-ABL']
        self.expect('DEPTH_BOUNDARY', store.submit, self.ws, handoff)
        handoff = self.l2(pid)
        handoff['targeted']['scope_statement'] = ''
        self.expect('INVALID_SCREENING_HANDOFF', store.submit, self.ws, handoff)


class GuardrailConsistencyTests(Workspace):
    def test_every_rule_recommendation_passes_its_own_guardrails(self):
        """Exhaustive over the deciding dimensions: the rules never propose what the guardrails refuse."""
        import itertools
        values = triage.RATINGS + ('UNKNOWN',)
        outcomes = set()
        for depth, sha in [('L0', None), ('L1', 'source'), ('L2', 'source')]:
            record = triage.new_record('P0001', {'title': 'Case'}, {'record_id': 'REC-01'})
            record['full_text'].update(current_sha256=sha, access_state='AVAILABLE' if sha else 'NOT_ATTEMPTED')
            item = {'item_id': 'I1', 'kind': 'ABSTRACT', 'label': 'Abstract', 'read_level': 'READ_IN_FULL'}
            for level in triage.SCREENING_DEPTHS[:triage.SCREENING_DEPTHS.index(depth) + 1]:
                record['passes'].append({'pass_id': level + '-01', 'depth': level, 'status': 'CURRENT', 'examined': [item],
                                         'source_sha256': None if level == 'L0' else sha, 'conflicts': []})
            for combination in itertools.product(values, repeat=len(triage.EXCLUSION_DIMENSIONS)):
                ratings = dict(zip(triage.EXCLUSION_DIMENSIONS, combination))
                record['assessments'] = [{'assessment_id': 'A01', 'target': triage.target_binding(TARGET), 'source_sha256': None,
                                          **assessment('I1', **ratings)}]
                proposed = triage.recommend(record, record['assessments'][0])
                route = decision(proposed['decision'], refs=('I1',), focus=['Named focus'], evidence_needed=['Named evidence'])
                try:
                    triage.apply_decision(record, route, TARGET)
                except RunError as exc:
                    self.fail(f'{depth} {ratings}: rules proposed {proposed["decision"]}, guardrail said {exc.code}: {exc}')
                outcomes.add(proposed['decision'])
                if 'UNKNOWN' in combination:
                    self.assertNotIn(proposed['decision'], {'EXCLUDE_FOR_TARGET', 'BACKGROUND_ONLY'}, ratings)
        self.assertEqual(outcomes, triage.DECISIONS)

    def test_applicability_alone_keeps_a_paper_out_of_exclusion(self):
        pid = self.add('An unrelated paper with a usable deployment note')
        store.submit(self.ws, self.l0(pid, **{**NONE, 'practical_applicability': 'MEDIUM'}))
        self.assertEqual(store.recommend(self.ws, pid)['decision'], 'BACKGROUND_ONLY')
        store.route(self.ws, pid, decision('BACKGROUND_ONLY'))
        self.expect('EXCLUSION_UNSUPPORTED', store.route, self.ws, pid, decision('EXCLUDE_FOR_TARGET', by='AGENT_JUDGMENT'))

    def test_single_unknown_dimension_defers_instead_of_demoting(self):
        pid = self.add('A paper whose usefulness cannot be judged yet')
        store.submit(self.ws, self.l0(pid, **{**NONE, 'research_utility': 'UNKNOWN'}))
        self.assertEqual(store.recommend(self.ws, pid)['decision'], 'DEFER_FOR_EVIDENCE')
        self.expect('EXCLUSION_UNSUPPORTED', store.route, self.ws, pid, decision('BACKGROUND_ONLY', by='AGENT_JUDGMENT'))
        status = store.route(self.ws, pid, decision('DEFER_FOR_EVIDENCE', evidence_needed=['The abstract']))
        self.assertEqual(status['next_action'], {'kind': 'OBTAIN_EVIDENCE', 'evidence_needed': ['The abstract'],
                                                 'instruction': status['next_action']['instruction']})
        self.assertEqual([row['next_action'] for row in store.queue(self.ws)['queue']], ['OBTAIN_EVIDENCE'])

    def test_ratings_cite_examined_items_and_nested_rows_keep_known_fields(self):
        pid = self.add()
        bare = self.l0(pid, **NONE)
        bare['assessment']['dimensions']['topic_relevance']['refs'] = []
        self.expect('INVALID_ASSESSMENT', store.submit, self.ws, bare)
        padded = self.l0(pid, topic_relevance='MEDIUM')
        padded['assessment']['target_links'][0].update(independent_review=True, verification='VERIFIED')
        store.submit(self.ws, padded)
        saved = self.record(pid)['assessments'][0]
        self.assertEqual(saved['target_links'], [{'question_id': 'Q1', 'relation': 'Describes an organizational mechanism.'}])
        self.assertNotIn('"VERIFIED"', json.dumps(self.record(pid)))

    def test_viewed_figures_and_notes_stay_inside_the_paper_workspace(self):
        pid = self.add()
        store.submit(self.ws, {**self.l0(pid, topic_relevance='MEDIUM'), 'decision': decision('PROMOTE_TO_L1')})
        self.attach(pid)
        outside = self.base/'elsewhere.png'
        outside.write_bytes(b'not the figure')
        figure = {'item_id': 'F-ARCH', 'kind': 'FIGURE', 'label': 'Figure 1', 'read_level': 'READ_IN_FULL',
                  'locator': {'physical_page': 1, 'object_label': 'Figure 1', 'checked': 'VERIFIED'}, 'actually_viewed': True}
        for ref in [str(outside), '../../../elsewhere.png']:
            skim = self.l1(pid, decision('REMAIN_AT_L1', refs=('S-INTRO',)), topic_relevance='MEDIUM')
            skim['examined'].append({**figure, 'artifact_refs': [ref]})
            self.expect('INVALID_SCREENING_HANDOFF', store.submit, self.ws, skim)
            skim = self.l1(pid, decision('REMAIN_AT_L1', refs=('S-INTRO',)), topic_relevance='MEDIUM')
            skim['notes_refs'] = [ref]
            self.expect('INVALID_SCREENING_HANDOFF', store.submit, self.ws, skim)
        inside = self.ws/'papers'/pid/'evidence'
        inside.mkdir()
        (inside/'fig1.png').write_bytes(b'opened crop')
        skim = self.l1(pid, decision('REMAIN_AT_L1', refs=('S-INTRO',)), topic_relevance='MEDIUM')
        skim['examined'].append({**figure, 'artifact_refs': ['evidence/fig1.png']})
        store.submit(self.ws, skim)
        saved = triage.examined_items(self.record(pid))['F-ARCH']
        self.assertEqual(saved['locator'], {'physical_page': 1, 'object_label': 'Figure 1'})

    def test_request_for_complete_reading_binds_routing_until_the_user_withdraws_it(self):
        pid = self.add('Radar retrieval of soil moisture')
        store.request_depth(self.ws, pid, 'L3', 'Read this one completely.')
        store.submit(self.ws, self.l0(pid, **NONE))
        record = self.record(pid)
        record['l3'] = {'run_path': 'elsewhere', 'source_sha256': None}  # a run was opened; it is not an acceptance
        store.save_record(self.ws, record)
        self.expect('USER_DEPTH_FLOOR', store.route, self.ws, pid, decision('EXCLUDE_FOR_TARGET'))
        record['l3'] = None
        store.save_record(self.ws, record)
        status = store.route(self.ws, pid, {'decision': 'EXCLUDE_FOR_TARGET', 'decided_by': 'USER',
                                           'reasons': ['The user dropped the paper.'], 'user_instruction': 'Never mind, skip it.'})
        self.assertIsNone(status['user_requested_depth'])
        self.assertEqual(status['next_action']['kind'], 'NONE')
        self.assertEqual([row['depth'] for row in self.record(pid)['depth_requests']], ['L3', None])


class TargetAndVersionTests(Workspace):
    def test_changed_research_target_suspends_earlier_screening_conclusions(self):
        pid = self.add('Radar retrieval of soil moisture')
        store.submit(self.ws, {**self.l0(pid, **NONE), 'decision': decision('EXCLUDE_FOR_TARGET')})
        self.assertEqual(store.flow(self.ws)['excluded_for_target'], 1)
        same_revision = {**TARGET, 'purpose': 'Remote sensing methods review.'}
        self.expect('INVALID_TARGET', store.set_target, self.ws, same_revision)
        result = store.set_target(self.ws, {**same_revision, 'revision': 2})
        self.assertEqual(result['papers_requiring_reassessment'], [pid])
        status = store.status(self.ws, pid)
        self.assertIsNone(status['routing']['decision'])
        self.assertEqual(status['routing']['stale_reason'], 'TARGET_CHANGED')
        self.assertEqual(status['next_action']['kind'], 'REASSESS_FOR_TARGET')
        self.assertEqual(status['tier'], 'METADATA_SCREENED')  # what was examined stays examined
        flow = store.flow(self.ws)
        self.assertEqual((flow['excluded_for_target'], flow['decisions_needing_reassessment']), (0, 1))
        self.expect('ASSESSMENT_REQUIRED', store.recommend, self.ws, pid)
        store.submit(self.ws, {**self.l0(pid, topic_relevance='HIGH', research_utility='HIGH'), 'decision': decision('PROMOTE_TO_L1')})
        self.assertEqual(store.status(self.ws, pid)['routing']['decision'], 'PROMOTE_TO_L1')
        self.assertEqual(len(self.record(pid)['decisions']), 2)  # the superseded exclusion stays in the log

    def test_unknown_record_versions_are_refused_not_migrated(self):
        pid = self.add()
        path = self.ws/'papers'/pid/'screening.json'
        before = json.loads(path.read_text(encoding='utf8'))
        path.write_text(json.dumps({**before, 'screening_schema_version': 2}), encoding='utf8')
        raw = path.read_bytes()
        self.expect('UNSUPPORTED_SCREENING_SCHEMA', store.submit, self.ws, self.l0(pid))
        self.expect('UNSUPPORTED_SCREENING_SCHEMA', store.status, self.ws, pid)
        self.assertEqual(path.read_bytes(), raw)

    def test_mismatched_source_is_isolated(self):
        pid = self.add()
        store.submit(self.ws, {**self.l0(pid, topic_relevance='MEDIUM'), 'decision': decision('PROMOTE_TO_L1')})
        self.attach(pid)
        skim = self.l1(pid, decision('REMAIN_AT_L1', refs=('S-INTRO',)), topic_relevance='MEDIUM')
        skim['identity_check'] = {'state': 'MISMATCH', 'basis': 'Page 1 shows a different title and authors.'}
        self.expect('IDENTITY_MISMATCH', store.submit, self.ws, skim)
        self.assertEqual(store.status(self.ws, pid)['tier'], 'METADATA_SCREENED')


if __name__ == '__main__':
    unittest.main()
