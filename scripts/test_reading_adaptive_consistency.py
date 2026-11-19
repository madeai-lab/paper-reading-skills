"""Regression tests for cross-record promotion consistency, target-dependent judgements, stated
criteria and user depth limits.

Static and simulated-flow tests on constructed records. They show the bookkeeping refuses the
specific inconsistencies below; they do not show that an agent reads or judges papers correctly.
"""
import copy
import json
from pathlib import Path

import reading_corpus as store
import reading_output_profiles as profiles
import reading_promotion as promotion
import reading_run_control as control
import reading_triage as triage
from reading_promotion_contracts import basis_errors, promoted, promotion_errors
from reading_run_check import inspect_run
from reading_run_records import RunError, digest
import test_reading_run_control as run_fixtures
from test_reading_pdf_elements import FakeParser
from test_reading_promotion import PromotionFixture
from test_reading_triage import NONE, TARGET, Workspace, assessment, decision

LEADS = 'handoffs/screening'
OTHER_TARGET = {**TARGET, 'revision': 2, 'purpose': 'How regularization affects generalization of deep networks.',
                'questions': [{'id': 'R1', 'text': 'Which regularizers are compared, and on what evidence?'}]}


def codes(errors):
    return {error['code'] for error in errors}


class PromotionRecordsTests(PromotionFixture):
    """The promotion record is the history; the packet binds to it; task.json copies the packet."""

    def setUp(self):
        super().setUp()
        self.pid = self.core_paper()
        self.run, _ = self.promote(self.pid)

    def edit(self, name, change):
        path = self.run/name
        data = json.loads(path.read_text(encoding='utf8'))
        change(data)
        path.write_text(json.dumps(data), encoding='utf8')

    def check(self):
        return inspect_run(self.run, require_review=False)

    def merge_error(self):
        (self.run/'01_scope_gaps.md').write_text('scope note', encoding='utf8')
        with self.assertRaises(RunError) as context:
            control.merge_handoff(self.run, {'writer_id': 'owner', 'gate_results': {'G0': {
                'decision': 'PENDING', 'evidence_refs': ['01_scope_gaps.md'], 'open_items': ['inventory']}}})
        return str(context.exception)

    def test_consistent_promotion_raises_no_promotion_error(self):
        found = codes(self.check())
        self.assertFalse({code for code in found if code.startswith('PROMOTION')}, found)
        record = json.loads((self.run/LEADS/'promotion.json').read_text(encoding='utf8'))
        self.assertEqual(record['screening_record_sha256'], digest(self.run/LEADS/'screening_record.json'))
        self.assertEqual(control.read(self.run/'task.json')['promotion'], control.read(self.run/'paper_packet.json')['promotion'])

    def test_task_and_packet_must_carry_the_same_binding(self):
        self.edit('task.json', lambda task: task['promotion'].update(from_depth='L2'))
        errors = [error for error in self.check() if error['code'] == 'PROMOTION_RECORDS_DISAGREE']
        self.assertEqual([(error['item'], 'from_depth' in error['next_action']) for error in errors], [('task.json', True)])
        self.assertIn('PROMOTION_RECORDS_DISAGREE', self.merge_error())

    def test_removing_the_binding_from_one_record_only_is_detected(self):
        self.edit('task.json', lambda task: task.pop('promotion'))
        self.assertIn('PROMOTION_RECORDS_DISAGREE', codes(self.check()))
        self.assertIn('PROMOTION_RECORDS_DISAGREE', self.merge_error())

    def test_packet_without_binding_is_still_recognized_through_task_or_record(self):
        self.edit('paper_packet.json', lambda packet: packet.pop('promotion'))
        self.assertIn('PROMOTION_RECORD_INVALID', codes(self.check()))
        (self.run/LEADS/'promotion.json').unlink()  # even with the record gone, the task copy still marks the run
        packet = control.read(self.run/'paper_packet.json')
        self.assertTrue(promoted(self.run, packet))
        self.assertIn('PROMOTION_RECORD_INVALID', codes(promotion_errors(self.run, packet)))

    def test_binding_edited_in_both_records_still_contradicts_the_promotion_record(self):
        for name in ['paper_packet.json', 'task.json']:
            self.edit(name, lambda data: data['promotion'].update(from_depth='L2', paper_id='P0099'))
        errors = [error for error in self.check() if error['code'] == 'PROMOTION_RECORDS_DISAGREE']
        self.assertEqual([error['item'] for error in errors], ['paper_packet.json'])
        self.assertIn('from_depth', errors[0]['next_action'])
        self.assertIn('paper_id', errors[0]['next_action'])

    def test_rewritten_promotion_record_or_snapshot_is_detected(self):
        self.edit(LEADS + '/promotion.json', lambda record: record.update(from_depth='L2'))
        self.assertIn('PROMOTION_RECORD_CHANGED', codes(self.check()))

    def test_snapshot_edit_is_detected_through_the_record(self):
        self.edit(LEADS + '/screening_record.json', lambda snapshot: snapshot['decisions'].pop())
        errors = [error for error in self.check() if error['code'] == 'PROMOTION_RECORD_CHANGED']
        self.assertEqual([error['item'] for error in errors], ['screening_record.json'])

    def forge(self, change):
        """Rewrite the snapshot and re-seal every hash, as a careful forger would."""
        self.edit(LEADS + '/screening_record.json', change)
        self.edit(LEADS + '/promotion.json', lambda record: record.update(
            screening_record_sha256=digest(self.run/LEADS/'screening_record.json')))
        sha = digest(self.run/LEADS/'promotion.json')
        for name in ['paper_packet.json', 'task.json']:
            self.edit(name, lambda data: data['promotion'].update(promotion_sha256=sha))

    def test_resealed_promotion_citing_a_stale_decision_or_source_is_refused(self):
        self.forge(lambda snapshot: snapshot['decisions'][-1].update(source_sha256='0' * 64))
        errors = [error for error in self.check() if error['code'].startswith('PROMOTION')]
        self.assertEqual([error['code'] for error in errors], ['PROMOTION_BASIS_STALE'])
        self.assertIn('another source version', errors[0]['next_action'])
        self.assertIn('PROMOTION_BASIS_STALE', self.merge_error())

    def test_upgrade_basis_rules(self):
        record = json.loads((self.run/LEADS/'promotion.json').read_text(encoding='utf8'))
        snapshot = json.loads((self.run/LEADS/'screening_record.json').read_text(encoding='utf8'))
        self.assertEqual(basis_errors(record, snapshot), [])
        superseded = copy.deepcopy(snapshot)
        superseded['decisions'].append({**snapshot['decisions'][-1], 'decision_id': 'D99', 'decision': 'REMAIN_AT_L1'})
        self.assertIn('not the current decision', basis_errors(record, superseded)[0])
        demoted = copy.deepcopy(snapshot)
        demoted['decisions'][-1]['decision'] = 'REMAIN_AT_L1'
        self.assertIn('does not promote', basis_errors(record, demoted)[0])
        retargeted = copy.deepcopy(snapshot)
        retargeted['decisions'][-1]['target'] = triage.target_binding(OTHER_TARGET)
        self.assertIn('another research target', basis_errors(record, retargeted)[0])
        reversioned = copy.deepcopy(snapshot)
        reversioned['full_text']['current_sha256'] = '1' * 64
        self.assertIn('another source version', basis_errors(record, reversioned)[0])
        self.assertIn('not the record of this paper', basis_errors(record, {**snapshot, 'paper_id': 'P0099'})[0])
        unrequested = {**record, 'trigger': {'kind': 'USER_REQUEST', 'ref': 'please'}}
        self.assertIn('no user request', basis_errors(unrequested, snapshot)[0])

    def test_target_changes_in_the_run_must_go_through_its_history(self):
        self.edit('paper_packet.json', lambda packet: packet.update(research_target=OTHER_TARGET))
        self.assertIn('PROMOTION_TARGET_MISMATCH', codes(self.check()))
        self.edit('paper_packet.json', lambda packet: packet.update(research_target=copy.deepcopy(TARGET)))
        control.set_target(self.run, OTHER_TARGET)  # the supported route records the earlier target
        self.assertNotIn('PROMOTION_TARGET_MISMATCH', codes(self.check()))

    def test_workspace_does_not_count_a_run_promoted_for_another_paper(self):
        self.edit('paper_packet.json', lambda packet: packet['promotion'].update(paper_id='P0099'))
        status = store.status(self.ws, self.pid)
        self.assertEqual((status['l3_state'], status['tier']), ('RUN_OF_ANOTHER_PAPER', 'SKIMMED'))


class AcceptanceStageTests(Workspace):
    """An accepted run stays accepted with a consistent promotion, and loses it when the records disagree."""

    def setUp(self):
        super().setUp()
        fixture = run_fixtures.ReadingRunControlTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.run = fixture.root
        self.fixture = fixture

    def seal(self):
        sha = self.fixture.packet['sources'][0]['sha256']
        leads = self.run/LEADS
        leads.mkdir(parents=True)
        (leads/'screening_record.json').write_text(json.dumps({
            'paper_id': 'P0001', 'full_text': {'current_sha256': sha}, 'depth': {'user_requested': 'L3'}, 'decisions': []}),
            encoding='utf8')
        trigger = {'kind': 'USER_REQUEST', 'ref': 'Read it completely.'}
        (leads/'promotion.json').write_text(json.dumps({
            'corpus_id': 'ws', 'paper_id': 'P0001', 'from_depth': 'L1', 'trigger': trigger, 'target': None,
            'source': {'sha256': sha}, 'reused': {'native_extraction': False},
            'screening_record_sha256': digest(leads/'screening_record.json')}), encoding='utf8')
        link = {'schema_version': 1, 'corpus_id': 'ws', 'paper_id': 'P0001', 'from_depth': 'L1', 'trigger': trigger,
                'promotion_ref': LEADS + '/promotion.json', 'promotion_sha256': digest(leads/'promotion.json'),
                'source_sha256': sha, 'extraction_reused': False}
        self.fixture.packet['promotion'] = link
        self.fixture.save()
        (self.run/'task.json').write_text(json.dumps({'promotion': link}), encoding='utf8')

    def test_untouched_old_run_is_not_asked_for_promotion_fields(self):
        self.assertFalse((self.run/'task.json').exists())
        self.assertFalse(promoted(self.run, self.fixture.packet))
        self.assertEqual(control.assess(self.run)['terminal_decision'], 'ACCEPTED')
        # A directory that merely looks similar, or a task file without the field, changes nothing.
        (self.run/LEADS).mkdir(parents=True)
        (self.run/LEADS/'my_old_notes.md').write_text('notes kept by the owner', encoding='utf8')
        (self.run/'task.json').write_text(json.dumps({'task_id': 'T1', 'review_mode': None}), encoding='utf8')
        self.assertFalse(promoted(self.run, self.fixture.packet))
        self.assertEqual(promotion_errors(self.run, self.fixture.packet), [])
        self.assertEqual(inspect_run(self.run), [])
        self.assertEqual(control.assess(self.run)['terminal_decision'], 'ACCEPTED')

    def test_acceptance_holds_only_while_the_promotion_records_agree(self):
        self.seal()
        self.assertEqual(inspect_run(self.run), [])
        self.assertEqual(control.assess(self.run)['terminal_decision'], 'ACCEPTED')
        task = json.loads((self.run/'task.json').read_text(encoding='utf8'))
        task['promotion']['source_sha256'] = '0' * 64
        (self.run/'task.json').write_text(json.dumps(task), encoding='utf8')
        assessment_now = control.assess(self.run)
        self.assertEqual((assessment_now['terminal_decision'], assessment_now['paper_accepted']), ('CONTINUE', False))
        self.assertIn('PROMOTION_RECORDS_DISAGREE', codes(assessment_now['next_action']['errors']))
        pid = self.add('The promoted paper')
        store.link_run(self.ws, pid, self.run)
        self.assertEqual(store.status(self.ws, pid)['tier'], 'UNSCREENED')  # not VERIFIED while the records disagree

    def test_acceptance_is_lost_when_only_the_packet_binding_is_removed(self):
        self.seal()
        del self.fixture.packet['promotion']
        self.fixture.save()
        self.assertEqual(control.assess(self.run)['terminal_decision'], 'CONTINUE')
        self.assertIn('PROMOTION_RECORD_INVALID', codes(inspect_run(self.run)))


class TargetChangeTests(Workspace):
    """Source facts and coverage stay; judgements made for the old target wait for reassessment."""

    def targeted_paper(self):
        ratings = dict(methodological_relevance='MEDIUM', research_utility='MEDIUM')
        pid = self.skimmed(**ratings)
        store.submit(self.ws, {**self.l2(pid), 'decision': decision('REMAIN_AT_L2', refs=('S-COORD',))})
        return pid

    def reassessment(self, pid, applies=True, **ratings):
        return {'writer_id': 'screener', 'paper_id': pid,
                'assessment': {**assessment('S-COORD', level='EXAMINED_SOURCE', evidence_adequacy='MEDIUM', **ratings),
                               'target_links': [{'question_id': 'R1', 'relation': 'Describes a regularizing design choice.'}]},
                'focus_applicability': [{'focus_id': 'F1', 'applies': applies, 'question_ids': ['R1'] if applies else [],
                                         'note': 'The replanning protocol was read as coordination, not as regularization.'}],
                'decision': decision('REMAIN_AT_L2', refs=('S-COORD',))}

    def test_reading_coverage_survives_and_target_judgements_are_suspended(self):
        pid = self.targeted_paper()
        before = store.status(self.ws, pid)
        self.assertEqual(before['permitted_use']['local_claims'], {'LC1': 'CANDIDATE_COMPARISON'})
        candidate = [{'synthesis_claim_id': 'SC', 'text': 'A candidate protocol.', 'evidence_basis': 'SCREENING_LIMITED',
                      'strength': 'CANDIDATE', 'support': [{'paper_id': pid, 'local_claim_id': 'LC1'}],
                      'limitation': 'Targeted reading of section 3.2 only; unreviewed.'}]
        self.assertTrue(store.check_synthesis(self.ws, candidate)['valid'])
        self.assertEqual(store.set_target(self.ws, OTHER_TARGET)['papers_requiring_reassessment'], [pid])
        after = store.status(self.ws, pid)
        # Kept: what was read, where, on which source bytes, and the tier that follows from it.
        self.assertEqual(after['coverage'], before['coverage'])
        self.assertEqual((after['tier'], after['effective_depth']), ('TARGETED_READ', 'L2'))
        label = after['target_dependent']['local_claims'][0]
        self.assertEqual((label['evidence_state'], label['attribution'], label['source_sha256']),
                         ('SUPPORTED', 'REPORTED_OBSERVATION', self.record(pid)['full_text']['current_sha256']))
        self.assertEqual(label['read_scope'][0]['label'], '3.2 Coordination')
        # Suspended: relevance, routing and the use of the local claim for the target.
        self.assertEqual(after['routing'], {**after['routing'], 'decision': None, 'stale_reason': 'TARGET_CHANGED'})
        self.assertEqual(label['target_applicability'], 'REASSESS_FOR_TARGET')
        self.assertEqual(after['permitted_use']['local_claims'], {'LC1': 'REASSESS_FOR_TARGET'})
        self.assertEqual(after['next_action']['kind'], 'REASSESS_FOR_TARGET')
        self.assertEqual(after['next_action']['focus_ids'], ['F1'])
        # Queue, exports and the stage-09 check do not treat the old judgement as current.
        self.assertEqual([(row['paper_id'], row['next_action']) for row in store.queue(self.ws)['queue']], [(pid, 'REASSESS_FOR_TARGET')])
        store.export(self.ws, 'matrix')
        row = json.loads((self.ws/'exports/comparison_matrix.json').read_text(encoding='utf8'))[0]
        self.assertEqual((row['decision'], row['decision_stale'], row['topic_relevance']), (None, 'TARGET_CHANGED', None))
        self.assertEqual((row['local_claims_usable_for_target'], row['local_claims_needing_reassessment']), (0, 1))
        store.export(self.ws, 'log')
        log = json.loads((self.ws/'exports/screening_log.json').read_text(encoding='utf8'))
        self.assertFalse(any(entry['current'] for entry in log))
        tiers = store.evidence_tiers(self.ws)['papers'][0]
        self.assertEqual((tiers['decision'], tiers['decision_stale'], tiers['local_claims'][0]['use']),
                         (None, 'TARGET_CHANGED', 'REASSESS_FOR_TARGET'))
        result = store.check_synthesis(self.ws, candidate)
        self.assertEqual([error['code'] for error in result['errors']], ['TARGET_APPLICABILITY_STALE'])
        background = [{**candidate[0], 'strength': 'BACKGROUND'}]
        self.assertTrue(store.check_synthesis(self.ws, background)['valid'])  # what the source says remains citable as background
        self.assertEqual(store.flow(self.ws)['decisions_needing_reassessment'], 1)

    def test_reassessment_restores_use_without_claiming_new_reading(self):
        pid = self.targeted_paper()
        store.set_target(self.ws, OTHER_TARGET)
        passes = copy.deepcopy(self.record(pid)['passes'])
        without_focus = self.reassessment(pid)
        del without_focus['focus_applicability']
        self.assertIn('F1', self.expect('INVALID_REASSESSMENT', store.reassess, self.ws, without_focus))
        smuggled = {**self.reassessment(pid), 'examined': [{'item_id': 'S-NEW'}]}
        self.expect('INVALID_REASSESSMENT', store.reassess, self.ws, smuggled)
        unknown_question = self.reassessment(pid)
        unknown_question['focus_applicability'][0]['question_ids'] = ['Q1']  # a question of the old target
        self.expect('INVALID_REASSESSMENT', store.reassess, self.ws, unknown_question)
        status = store.reassess(self.ws, self.reassessment(pid, methodological_relevance='MEDIUM', research_utility='MEDIUM'))
        record = self.record(pid)
        self.assertEqual(record['passes'], passes)  # no pass was added or altered
        self.assertIs(record['assessments'][-1]['reading_performed'], False)
        self.assertEqual(record['assessments'][-1]['kind'], 'REASSESSMENT')
        self.assertEqual(status['permitted_use']['local_claims'], {'LC1': 'CANDIDATE_COMPARISON'})
        self.assertEqual(status['target_dependent']['focus_applicability']['F1']['question_ids'], ['R1'])
        self.assertEqual((status['routing']['decision'], status['next_action']['kind']), ('REMAIN_AT_L2', 'NONE'))

    def test_focus_judged_not_applicable_stays_a_source_note(self):
        pid = self.targeted_paper()
        store.set_target(self.ws, OTHER_TARGET)
        payload = self.reassessment(pid, applies=False, **NONE)
        payload['assessment']['target_links'] = []
        payload['decision'] = decision('EXCLUDE_FOR_TARGET', refs=('S-COORD',))
        status = store.reassess(self.ws, payload)
        self.assertEqual(status['permitted_use']['local_claims'], {'LC1': 'SOURCE_NOTE_ONLY'})
        self.assertEqual((status['tier'], status['routing']['decision']), ('TARGETED_READ', 'EXCLUDE_FOR_TARGET'))
        result = store.check_synthesis(self.ws, [{'synthesis_claim_id': 'SC', 'text': 'A candidate.', 'evidence_basis': 'SCREENING_LIMITED',
                                                 'strength': 'CANDIDATE', 'support': [{'paper_id': pid, 'local_claim_id': 'LC1'}],
                                                 'limitation': 'Targeted reading only.'}])
        self.assertEqual([error['code'] for error in result['errors']], ['TARGET_APPLICABILITY_STALE'])

    def test_user_scope_instruction_is_carried_into_the_reassessment_step(self):
        """Seen in a real trial: after a target change an agent read far beyond 'only the appendix'."""
        limited = self.base/'scoped'
        store.init_corpus(limited, 'owner', copy.deepcopy(TARGET), max_depth='L2', instruction='No complete reading this round.')
        self.ws = limited
        pid = self.add()
        store.submit(self.ws, self.l0(pid, topic_relevance='MEDIUM'))
        store.request_depth(self.ws, pid, 'L2', 'For this paper read only the appendix; skip the rest.')
        self.attach(pid)
        store.submit(self.ws, self.l2(pid))
        store.set_target(self.ws, OTHER_TARGET)
        status = store.status(self.ws, pid)
        said = [(row['applies_to'], row['kind'], row['depth'], row['user_instruction']) for row in status['standing_user_instructions']]
        self.assertEqual(said, [('WORKSPACE', 'LIMIT', 'L2', 'No complete reading this round.'),
                                ('PAPER', 'REQUEST', 'L2', 'For this paper read only the appendix; skip the rest.')])
        step = status['next_action']
        self.assertEqual(step['kind'], 'REASSESS_FOR_TARGET')
        self.assertEqual([row['user_instruction'] for row in step['standing_user_instructions']],
                         ['For this paper read only the appendix; skip the rest.'])
        self.assertIn('not a new permission', step['instruction'])

    def test_fresh_decision_alone_does_not_revive_the_old_focus(self):
        pid = self.targeted_paper()
        store.set_target(self.ws, OTHER_TARGET)
        store.route(self.ws, pid, {'decision': 'PROMOTE_TO_L3', 'decided_by': 'USER', 'reasons': ['The user wants it read.'],
                                   'user_instruction': 'Read it completely.'})
        status = store.status(self.ws, pid)
        self.assertEqual(status['routing']['decision'], 'PROMOTE_TO_L3')
        self.assertEqual(status['permitted_use']['local_claims'], {'LC1': 'REASSESS_FOR_TARGET'})
        self.assertEqual(status['next_action']['kind'], 'REASSESS_FOR_TARGET')

    def test_skimmed_paper_is_reassessed_without_resubmitting_its_card(self):
        pid = self.skimmed(route=decision('REMAIN_AT_L1', refs=('S-INTRO',)), topic_relevance='MEDIUM')
        card = triage.latest_pass(self.record(pid), 'L1')['card']
        store.set_target(self.ws, OTHER_TARGET)
        payload = {'writer_id': 'screener', 'paper_id': pid,
                   'assessment': {**assessment('S-INTRO', level='AUTHOR_STATEMENT', evidence_adequacy='MEDIUM', **NONE), 'target_links': []},
                   'decision': decision('EXCLUDE_FOR_TARGET', refs=('S-INTRO',))}
        status = store.reassess(self.ws, payload)
        self.assertEqual((status['tier'], status['routing']['decision']), ('SKIMMED', 'EXCLUDE_FOR_TARGET'))
        self.assertEqual(triage.latest_pass(self.record(pid), 'L1')['card'], card)
        store.set_target(self.ws, None)
        self.expect('TARGET_REQUIRED', store.reassess, self.ws, payload)

    def test_card_and_labels_show_scope_source_attribution_and_review_status(self):
        pid = self.targeted_paper()
        card = (self.ws/profiles.render_card(self.ws, pid)['file']).read_text(encoding='utf8')
        sha = self.record(pid)['full_text']['current_sha256']
        for expected in ['Independent review: none', 'source version `%s`' % sha, 'Attribution: REPORTED_OBSERVATION',
                         'Use for the current target: CANDIDATE_COMPARISON', '3.2 Coordination', 'Scope of this pass:',
                         'The paper as a whole was not verified']:
            self.assertIn(expected, card)
        label = store.evidence_tiers(self.ws)['papers'][0]['local_claims'][0]
        self.assertEqual((label['independent_review'], label['complete_paper_verified'], label['writer_id']), ('NONE', False, 'reader'))
        store.set_target(self.ws, OTHER_TARGET)
        self.assertEqual(profiles.check(self.ws, pid, 'PAPER_CARD')['errors'][0]['code'], 'OUTPUT_STALE')
        card = (self.ws/profiles.render_card(self.ws, pid)['file']).read_text(encoding='utf8')
        self.assertIn('chosen for another research target', card)
        self.assertIn('Use for the current target: REASSESS_FOR_TARGET', card)


class StatedCriterionTests(Workspace):
    """Unknown ratings never exclude; an explicit violation of a stated criterion is not held hostage by them."""

    CRITERIA = [{'id': 'C-NN', 'text': 'The paper does not study training of neural networks.'}]

    def setUp(self):
        super().setUp()
        self.ws = self.base/'criteria'
        store.init_corpus(self.ws, 'owner', copy.deepcopy(TARGET), criteria=copy.deepcopy(self.CRITERIA))
        self.pid = self.add('Radar retrieval of soil moisture')
        # The abstract shows the topic; transferability and applicability cannot be judged from it.
        store.submit(self.ws, self.l0(self.pid, **{**NONE, 'transferability': 'UNKNOWN', 'practical_applicability': 'UNKNOWN'}))

    def exclusion(self, **changes):
        return {**decision('EXCLUDE_FOR_TARGET', by='AGENT_JUDGMENT'), 'basis': 'STATED_CRITERION', 'exclusion_criterion': 'C-NN',
                'criterion_evidence': [{'text': 'The abstract describes radar retrieval of soil moisture; no network is trained.',
                                        'from_items': ['M-ABS']}], **changes}

    def test_unknown_ratings_still_block_a_rating_based_exclusion(self):
        self.assertEqual(store.recommend(self.ws, self.pid)['decision'], 'DEFER_FOR_EVIDENCE')
        self.expect('EXCLUSION_UNSUPPORTED', store.route, self.ws, self.pid, decision('EXCLUDE_FOR_TARGET', by='AGENT_JUDGMENT'))
        self.expect('EXCLUSION_UNSUPPORTED', store.route, self.ws, self.pid,
                    {**decision('EXCLUDE_FOR_TARGET', by='AGENT_JUDGMENT'), 'exclusion_criterion': 'C-NN'})  # an ID alone is no evidence

    def test_explicit_criterion_violation_excludes_despite_unrelated_unknowns(self):
        status = store.route(self.ws, self.pid, self.exclusion())
        self.assertEqual((status['routing']['decision'], status['next_action']['kind']), ('EXCLUDE_FOR_TARGET', 'NONE'))
        saved = self.record(self.pid)['decisions'][-1]
        self.assertEqual((saved['basis'], saved['exclusion_criterion'], saved['rule_recommendation']),
                         ('STATED_CRITERION', 'C-NN', 'DEFER_FOR_EVIDENCE'))
        self.assertEqual(saved['criterion_evidence'][0]['from_items'], ['M-ABS'])
        self.assertEqual(saved['criterion_sha256'], triage.criterion_sha(self.CRITERIA[0]))
        self.assertEqual(store.flow(self.ws)['exclusions_by_criterion_or_decider'], {'C-NN': 1})
        store.export(self.ws, 'log')
        entry = json.loads((self.ws/'exports/screening_log.json').read_text(encoding='utf8'))[-1]
        self.assertEqual((entry['basis'], entry['exclusion_criterion'], entry['current']), ('STATED_CRITERION', 'C-NN', True))

    def test_criterion_exclusion_needs_a_stated_criterion_and_source_evidence(self):
        self.expect('EXCLUSION_CRITERION_REQUIRED', store.route, self.ws, self.pid, self.exclusion(exclusion_criterion='C-MADE-UP'))
        self.expect('EXCLUSION_UNSUPPORTED', store.route, self.ws, self.pid, self.exclusion(criterion_evidence=[]))
        self.expect('EXCLUSION_UNSUPPORTED', store.route, self.ws, self.pid,
                    self.exclusion(criterion_evidence=[{'text': 'Nothing in the record mentions networks.', 'from_items': []}]))
        self.expect('EXCLUSION_UNSUPPORTED', store.route, self.ws, self.pid,
                    self.exclusion(criterion_evidence=[{'text': 'Body text.', 'from_items': ['S-NOT-EXAMINED']}]))
        self.expect('INVALID_DECISION', store.route, self.ws, self.pid, self.exclusion(decided_by='ROUTER_RULES'))
        self.expect('INVALID_DECISION', store.route, self.ws, self.pid,
                    {**self.exclusion(), 'decision': 'BACKGROUND_ONLY'})  # the criterion route exists for exclusion only
        plain = self.base/'plain'
        store.init_corpus(plain, 'owner', copy.deepcopy(TARGET))
        self.ws = plain
        other = self.add('Radar retrieval of soil moisture')
        store.submit(self.ws, self.l0(other, **{**NONE, 'transferability': 'UNKNOWN'}))
        self.expect('EXCLUSION_CRITERION_REQUIRED', store.route, self.ws, other, self.exclusion())  # nothing was stated beforehand

    def test_user_requested_depth_outranks_a_criterion(self):
        store.request_depth(self.ws, self.pid, 'L3', 'Read it completely anyway.')
        self.expect('USER_DEPTH_FLOOR', store.route, self.ws, self.pid, self.exclusion())

    def test_changed_criterion_suspends_exclusions_that_cited_it(self):
        store.route(self.ws, self.pid, self.exclusion())
        result = store.set_criteria(self.ws, [{'id': 'C-NN', 'text': 'The paper does not study machine learning at all.'}])
        self.assertEqual(result['papers_requiring_a_new_decision'], [self.pid])
        status = store.status(self.ws, self.pid)
        self.assertEqual((status['routing']['decision'], status['routing']['stale_reason']), (None, 'CRITERION_CHANGED'))
        self.assertEqual(status['next_action']['kind'], 'RECORD_ROUTING_DECISION')
        self.assertEqual(store.flow(self.ws)['excluded_for_target'], 0)
        self.assertEqual(len(store.load_corpus(self.ws)['protocol']['criteria_history']), 1)
        store.route(self.ws, self.pid, self.exclusion())
        self.assertEqual(store.status(self.ws, self.pid)['routing']['decision'], 'EXCLUDE_FOR_TARGET')


class UserDepthLimitTests(PromotionFixture):
    """A recommendation to read deeper is recorded; reading deeper than the user allowed is not performed."""

    def test_abstract_only_workspace_records_recommendations_but_reads_no_body(self):
        limited = self.base/'abstracts'
        self.expect('USER_INSTRUCTION_REQUIRED', store.init_corpus, self.base/'bad', 'owner', copy.deepcopy(TARGET), max_depth='L0')
        store.init_corpus(limited, 'owner', copy.deepcopy(TARGET), max_depth='L0', instruction='Only look at the abstracts.')
        self.ws = limited
        pid = self.add()
        ratings = dict(topic_relevance='HIGH', research_utility='HIGH')
        status = store.submit(self.ws, {**self.l0(pid, **ratings), 'decision': decision('PROMOTE_TO_L1')})
        self.assertEqual(status['user_depth_ceiling'], 'L0')
        self.assertEqual(status['routing']['decision'], 'PROMOTE_TO_L1')  # the recommendation is on record
        self.assertEqual(status['next_action']['kind'], 'UPGRADE_NEEDS_USER')
        self.assertEqual((status['next_action']['recommended_depth'], status['next_action']['allowed_depth']), ('L1', 'L0'))
        recommended = store.recommend(self.ws, pid)
        self.assertEqual((recommended['decision'], recommended['requires_user_approval']), ('PROMOTE_TO_L1', True))
        self.attach(pid)  # holding the file is not reading it
        self.expect('USER_DEPTH_CEILING', store.submit, self.ws, self.l1(pid, decision('PROMOTE_TO_L3', by='AGENT_JUDGMENT', refs=('S-INTRO',)), **ratings))
        self.expect('USER_DEPTH_CEILING', promotion.promote, self.ws, pid, self.base/'run', 'owner')
        self.assertEqual(store.status(self.ws, pid)['tier'], 'METADATA_SCREENED')
        self.assertEqual([row['next_action'] for row in store.queue(self.ws)['queue']], ['UPGRADE_NEEDS_USER'])
        # The user asks to continue with this paper: the limit is lifted for it, and only for it.
        store.request_depth(self.ws, pid, 'L1', 'OK, skim that one.')
        status = store.submit(self.ws, self.l1(pid, decision('PROMOTE_TO_L3', by='AGENT_JUDGMENT', refs=('S-INTRO',)), **ratings))
        # The request let L1 through and no further: complete reading is recommended, not started.
        self.assertEqual((status['tier'], status['user_depth_ceiling'], status['next_action']['kind']),
                         ('SKIMMED', 'L1', 'UPGRADE_NEEDS_USER'))
        other = self.add('Another candidate in the same workspace')
        self.assertEqual(store.status(self.ws, other)['user_depth_ceiling'], 'L0')

    def test_quick_judgement_limit_keeps_complete_reading_a_recommendation(self):
        pid = self.add()
        store.request_depth(self.ws, pid, 'L1', 'Quickly judge whether this is worth reading.')
        status = store.limit_depth(self.ws, pid, 'L1', 'Quickly judge whether this is worth reading.')
        self.assertEqual((status['user_requested_depth'], status['user_depth_ceiling']), ('L1', 'L1'))
        self.attach(pid)
        ratings = dict(topic_relevance='HIGH', methodological_relevance='HIGH', research_utility='HIGH')
        status = store.submit(self.ws, self.l1(pid, decision('PROMOTE_TO_L3', refs=('S-INTRO', 'T-MAIN')), **ratings))
        self.assertEqual((status['tier'], status['routing']['decision'], status['next_action']['kind']),
                         ('SKIMMED', 'PROMOTE_TO_L3', 'UPGRADE_NEEDS_USER'))
        self.expect('USER_DEPTH_CEILING', promotion.promote, self.ws, pid, self.base/'run', 'owner')
        self.assertFalse((self.base/'run').exists())
        store.request_depth(self.ws, pid, 'L3', 'Yes, go on and read it completely.')
        self.assertEqual(store.status(self.ws, pid)['next_action']['kind'], 'PROMOTE_L3')
        run, _ = self.promote(pid)
        self.assertEqual(control.read(run/'paper_packet.json')['promotion']['trigger']['kind'], 'USER_REQUEST')

    def test_request_within_an_existing_limit_leaves_the_limit_in_place(self):
        limited = self.base/'no-complete-reading'
        store.init_corpus(limited, 'owner', copy.deepcopy(TARGET), max_depth='L2', instruction='No complete reading this round.')
        self.ws = limited
        pid = self.add()
        status = store.request_depth(self.ws, pid, 'L2', 'For this one read only the appendix.')
        self.assertEqual((status['user_requested_depth'], status['user_depth_ceiling']), ('L2', 'L2'))
        self.assertIsNone(self.record(pid)['depth'].get('ceiling'))  # the workspace limit still governs; nothing was overridden
        self.expect('USER_DEPTH_CEILING', promotion.promote, self.ws, pid, self.base/'run', 'owner', source=self.pdf())
        status = store.route(self.ws, pid, {'decision': 'PROMOTE_TO_L3', 'decided_by': 'USER', 'reasons': ['The user decided.'],
                                           'user_instruction': 'Go ahead and read it completely.'})
        self.assertEqual((status['user_depth_ceiling'], status['next_action']['kind']), (None, 'PROMOTE_L3'))

    def test_evidence_gap_with_the_paper_in_hand_routes_to_a_skim_and_can_be_previewed(self):
        pid = self.add()
        unknown = dict(topic_relevance='LOW', methodological_relevance='UNKNOWN', transferability='UNKNOWN')
        store.submit(self.ws, self.l0(pid, **unknown))
        self.assertEqual(store.recommend(self.ws, pid)['decision'], 'DEFER_FOR_EVIDENCE')  # nothing to read yet
        self.attach(pid)
        proposed = store.recommend(self.ws, pid)
        self.assertEqual((proposed['decision'], proposed['rule']), ('PROMOTE_TO_L1', 'EVIDENCE_GAP_SKIM'))
        store.route(self.ws, pid, decision('PROMOTE_TO_L1'))
        before = (self.ws/'papers'/pid/'screening.json').read_bytes()
        skim = self.l1(pid, None, topic_relevance='MEDIUM')
        skim.pop('decision')
        preview = store.recommend(self.ws, pid, skim)
        self.assertEqual(preview['decision'], 'REMAIN_AT_L1')
        self.assertIn('nothing was written', preview['preview'])
        self.assertEqual((self.ws/'papers'/pid/'screening.json').read_bytes(), before)
        store.submit(self.ws, {**skim, 'decision': decision(preview['decision'], refs=('S-INTRO',))})
        flow = store.flow(self.ws)
        self.assertEqual((flow['reached_L1_or_deeper'], flow['passes_by_depth']), (1, {'L0': 1, 'L1': 1, 'L2': 0}))

    def test_later_limit_withdraws_an_earlier_request_for_more(self):
        pid = self.add()
        store.request_depth(self.ws, pid, 'L3', 'Read it completely.')
        status = store.limit_depth(self.ws, pid, 'L0', 'Actually, just the abstract; I have ten minutes.')
        self.assertEqual((status['user_requested_depth'], status['user_depth_ceiling']), (None, 'L0'))
        self.assertEqual([row.get('depth', row.get('limit')) for row in self.record(pid)['depth_requests']], ['L3', 'L0'])
        self.expect('USER_DEPTH_CEILING', promotion.promote, self.ws, pid, self.base/'run', 'owner', source=self.pdf())
        self.expect('USER_INSTRUCTION_REQUIRED', store.limit_depth, self.ws, pid, 'L1', '')
        self.expect('USER_INSTRUCTION_REQUIRED', store.limit_depth, self.ws, None, 'L3', 'everything')

    def test_request_for_complete_reading_is_unaffected_by_limits_elsewhere(self):
        pid = self.add('A paper to verify')
        other = self.add('A paper to glance at')
        store.limit_depth(self.ws, other, 'L0', 'Abstract only for this one.')
        store.request_depth(self.ws, pid, 'L3', 'Read this paper completely.')
        store.submit(self.ws, self.l0(pid, **NONE))
        self.expect('USER_DEPTH_FLOOR', store.route, self.ws, pid, decision('EXCLUDE_FOR_TARGET'))
        self.assertEqual(store.status(self.ws, pid)['next_action']['kind'], 'PROMOTE_L3')
        self.assertEqual(store.status(self.ws, other)['user_depth_ceiling'], 'L0')


class RealTrialFindingsTests(PromotionFixture):
    """Defects observed when agents used the skill on real papers; each test fails on the earlier behaviour."""

    def skim_with_conflict(self, kind, **ratings):
        self.serial = getattr(self, 'serial', 0) + 1
        pid = self.add('A paper with an unresolved question number %d' % self.serial)
        store.request_depth(self.ws, pid, 'L1', 'Quickly judge it.')
        self.attach(pid)
        ratings.setdefault('evidence_adequacy', 'MEDIUM')
        skim = self.l1(pid, None, **ratings)
        skim.pop('decision')
        skim['conflicts'] = [{'conflict_id': 'K1', 'kind': kind, 'status': 'OPEN', 'items': ['S-ABS', 'T-MAIN'],
                              'description': 'The record abstract and the attached file disagree.'}]
        return pid, skim

    def recommend_after(self, pid, skim):
        probe = triage.apply_handoff(self.record(pid), {**skim, 'decision': decision('DEFER_FOR_EVIDENCE', by='AGENT_JUDGMENT',
                                                                                 refs=('S-INTRO',), evidence_needed=['x'])},
                                     TARGET, self.ws/'papers'/pid, 'handoffs/probe.json')
        return triage.recommend(probe, probe['assessments'][-1])

    def test_open_conflict_does_not_force_reading_of_a_paper_with_no_other_reason(self):
        pid, skim = self.skim_with_conflict('CONTENT')  # every deciding dimension LOW
        proposed = self.recommend_after(pid, skim)
        self.assertEqual(proposed['decision'], 'BACKGROUND_ONLY')
        self.assertTrue(any(line.startswith('OPEN_CONFLICT') for line in proposed['use_restrictions']))
        # Honest recording now passes: the conflict stays OPEN and the rule output can be recorded as it is.
        status = store.submit(self.ws, {**skim, 'decision': decision('BACKGROUND_ONLY', refs=('S-INTRO',))})
        self.assertEqual((status['open_conflicts'], status['routing']['decision']), (['K1'], 'BACKGROUND_ONLY'))

    def test_open_version_difference_restricts_use_without_routing_deeper(self):
        pid, skim = self.skim_with_conflict('VERSION_DIFFERENCE', topic_relevance='MEDIUM')
        proposed = self.recommend_after(pid, skim)
        self.assertEqual(proposed['decision'], 'REMAIN_AT_L1')
        self.assertTrue(any(line.startswith('VERSION_DIFFERENCE') for line in proposed['use_restrictions']))
        related, content = self.skim_with_conflict('CONTENT', topic_relevance='MEDIUM')
        self.assertEqual(self.recommend_after(related, content)['decision'], 'PROMOTE_TO_L2')  # a content conflict still does
        content['conflicts'][0]['kind'] = 'TYPO'
        self.expect('INVALID_SCREENING_HANDOFF', store.submit, self.ws, {**content, 'decision': decision('REMAIN_AT_L1', refs=('S-INTRO',))})

    def test_scaffold_guidance_is_ignored_and_text_items_may_cite_a_checked_image(self):
        import reading_triage_control as cli
        pid = self.add()
        template = cli.handoff_template(self.ws, pid, 'L0', 'screener')
        self.assertIn('NOT_ASSESSED', template['_guide']['assessment.evidence_level'])
        handoff = {**self.l0(pid, topic_relevance='MEDIUM'), '_guide': template['_guide'], 'decision': decision('PROMOTE_TO_L1')}
        store.submit(self.ws, handoff)
        self.attach(pid)
        skim = self.l1(pid, decision('REMAIN_AT_L1', refs=('S-INTRO',)), topic_relevance='MEDIUM')
        algorithm = {'item_id': 'A-ALG1', 'kind': 'ALGORITHM', 'label': 'Algorithm 1', 'read_level': 'READ_IN_FULL',
                     'locator': {'physical_page': 1, 'object_label': 'Algorithm 1'}, 'actually_viewed': True}
        skim['examined'].append({**algorithm, 'artifact_refs': ['../outside.png']})
        self.expect('INVALID_SCREENING_HANDOFF', store.submit, self.ws, copy.deepcopy(skim))
        evidence = self.ws/'papers'/pid/'evidence'
        evidence.mkdir()
        (evidence/'alg1.png').write_bytes(b'rendered crop')
        skim['examined'][-1]['artifact_refs'] = ['evidence/alg1.png']
        store.submit(self.ws, skim)
        saved = triage.examined_items(self.record(pid))['A-ALG1']
        self.assertEqual((saved['artifact_refs'], saved['checked_against_image']), (['evidence/alg1.png'], True))

    def test_passing_mention_of_a_mechanism_is_noted_not_routed_to_targeted_reading(self):
        touched = dict(methodological_relevance='MEDIUM', transferability='MEDIUM', research_utility='LOW', evidence_adequacy='LOW')
        pid, skim = self.skim_with_conflict('CONTENT', **touched)
        skim['conflicts'] = []
        proposed = self.recommend_after(pid, skim)
        self.assertEqual(proposed['decision'], 'BACKGROUND_ONLY')
        self.assertTrue(any(line.startswith('MECHANISM_NOTED') for line in proposed['trace']))
        useful, skim = self.skim_with_conflict('CONTENT', **{**touched, 'research_utility': 'MEDIUM'})
        skim['conflicts'] = []
        proposed = self.recommend_after(useful, skim)
        self.assertEqual((proposed['decision'], proposed['rule']), ('PROMOTE_TO_L2', 'SPECIFIC_MECHANISM'))

    def test_term_search_replaces_page_reads_and_card_history_is_kept(self):
        import reading_resources as resources
        pid = self.core_paper()
        found = promotion.find_text(self.ws, pid, ['native', 'absent-term'])
        self.assertEqual((found['counts'], found['pages_with_hits'], found['purpose']),
                         ({'native': 1, 'absent-term': 0}, [1], 'NAVIGATION_ONLY'))
        self.assertIn('Native evidence', found['hits'][0]['snippet'])
        usage = resources.summary(self.ws, pid)
        self.assertEqual((usage['by_kind'].get('TEXT_SEARCH'), usage['page_reads']['calls']), (1, 0))
        self.expect('INVALID_ARGUMENT', promotion.find_text, self.ws, pid, [])
        first = (self.ws/profiles.render_card(self.ws, pid)['file']).read_text(encoding='utf8')
        store.route(self.ws, pid, decision('REMAIN_AT_L1', by='AGENT_JUDGMENT', refs=('S-INTRO',)))
        profiles.render_card(self.ws, pid)
        kept = list((self.ws/'outputs'/pid/'history').glob('PAPER_CARD.*.md'))
        self.assertEqual([path.read_text(encoding='utf8') for path in kept], [first])

    def test_deeper_pass_supersedes_earlier_unexamined_lists_and_flags(self):
        ratings = dict(methodological_relevance='MEDIUM', research_utility='MEDIUM')
        pid = self.skimmed(**ratings)
        skimmed = store.status(self.ws, pid)
        self.assertEqual([row['label'] for row in skimmed['coverage']['not_examined']], ['4.2 Ablations', 'Appendix A'])
        self.assertEqual([flag['code'] for flag in skimmed['uncertainty_flags']], ['ABLATIONS_NOT_READ'])  # not the L0 BODY_NOT_READ
        status = store.submit(self.ws, self.l2(pid))
        self.assertEqual([row['label'] for row in status['coverage']['not_examined']], ['Sections 5-6 and appendices'])
        self.assertEqual(status['uncertainty_flags'], [])
        card = (self.ws/profiles.render_card(self.ws, pid)['file']).read_text(encoding='utf8')
        self.assertNotIn('Metadata screening does not open the paper', card)
        self.assertNotIn('BODY_NOT_READ', card)
        self.assertEqual(len(self.record(pid)['passes'][0]['not_examined']), 1)  # the earlier list stays in its pass

    def test_located_leads_and_crop_receipts_enter_the_run_as_material_to_verify(self):
        """Seen in the real upgrade: copied crops went unused and local claims had to be re-found."""
        import hashlib
        ratings = dict(topic_relevance='HIGH', methodological_relevance='HIGH', research_utility='HIGH')
        pid = self.skimmed(route=decision('PROMOTE_TO_L2', by='AGENT_JUDGMENT', refs=('S-INTRO',), focus=['3.2 Coordination']), **ratings)
        store.submit(self.ws, {**self.l2(pid), 'decision': decision('PROMOTE_TO_L3', by='AGENT_JUDGMENT', refs=('S-COORD',))})
        promotion.extract(self.ws, pid, parser=FakeParser())
        version = self.record(pid)['full_text']['versions'][0]
        evidence = self.ws/'papers'/pid/version['directory']/'evidence'
        evidence.mkdir()
        (evidence/'fig1.png').write_bytes(b'rendered figure')
        (evidence/'loose.png').write_bytes(b'image without a receipt')
        control.write(evidence/'receipts.json', {'fig1.png': {
            'source_sha256': version['sha256'], 'physical_page': 1, 'bbox': [10, 20, 110, 120], 'scale': 3.0, 'pixel_size': [300, 300],
            'image_sha256': hashlib.sha256(b'rendered figure').hexdigest(), 'page_ref': 'source_elements/page-0001.json'}})
        run, result = self.promote(pid)
        record = json.loads((run/LEADS/'promotion.json').read_text(encoding='utf8'))
        crops = {Path(row['path']).name: row for row in record['reused']['rendered_crops']}
        self.assertEqual((crops['fig1.png']['physical_page'], crops['fig1.png']['bbox']), (1, [10, 20, 110, 120]))
        self.assertIsNone(crops['loose.png']['bbox'])  # no receipt: location unknown, and said so
        leads = json.loads((run/LEADS/'claim_leads.json').read_text(encoding='utf8'))
        claim = next(row for row in leads if row['lead_id'] == 'LEAD-LC1')
        self.assertEqual((claim['status'], claim['evidence_state_at_screening']), ('TO_VERIFY', 'SUPPORTED'))
        self.assertEqual(claim['where_to_check'][0]['locator'], {'physical_page': 1, 'section': '3.2 Coordination'})
        self.assertTrue(any(row['lead_id'].startswith('LEAD-CARD-headline_evidence') for row in leads))
        text = (run/LEADS/'leads.md').read_text(encoding='utf8')
        self.assertIn('bbox [10, 20, 110, 120]', text)
        self.assertIn('no render receipt', text)
        self.assertIn('some will be wrong', text)
        # Nothing was inherited, and the checklist cannot be merged or used as evidence.
        packet = control.read(run/'paper_packet.json')
        self.assertEqual((packet['claims'], packet['units'], packet['gate_results']['G1']['decision']), ([], [], 'PENDING'))
        with self.assertRaises(RunError):
            control.merge_handoff(run, {'writer_id': 'owner', 'claims': leads})
        self.sync(run)
        with self.assertRaises(RunError) as context:
            control.merge_handoff(run, {'writer_id': 'owner', 'units': [{
                'unit_id': 'S1', 'read_state': 'CHECKED', 'understanding_note': 'Confirmed by the lead list.',
                'evidence_refs': ['handoffs/screening/claim_leads.json']}]})
        self.assertIn('SCREENING_NOTE_NOT_EVIDENCE', str(context.exception))
        self.assertFalse({code for code in codes(inspect_run(run, require_review=False)) if code.startswith('PROMOTION')})

    def test_helpers_run_under_an_isolated_interpreter_and_explain_read_limits(self):
        import subprocess
        import sys
        script = Path(__file__).with_name('reading_triage_control.py')
        result = subprocess.run([sys.executable, '-I', str(script), 'flow', str(self.ws)], capture_output=True, text=True, encoding='utf8')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['papers'], 0)
        for name in ['reading_run_control.py', 'reading_run_check.py']:
            result = subprocess.run([sys.executable, '-I', str(script.with_name(name)), '--help'], capture_output=True, text=True, encoding='utf8')
            self.assertEqual(result.returncode, 0, name + result.stderr)
        pid = self.core_paper()
        message = self.expect('ELEMENT_READ_LIMIT', promotion.read_pages, self.ws, pid, [1, 2, 3, 4, 5])
        self.assertNotIn('read-section', message)
        self.assertEqual(triage.skim_plan('SURVEY')['paper_type'], 'SURVEY')


if __name__ == '__main__':
    import unittest
    unittest.main()
