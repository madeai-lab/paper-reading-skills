"""Policy-2 workflows on synthetic records only. No model, PDF retrieval or real-paper run."""
import copy

import reading_corpus as store
import reading_resources as usage
import reading_triage as triage
from reading_run_records import write
from test_reading_triage import TARGET, Workspace, decision


class ResearchReadingTests(Workspace):
    def test_general_explanation_starts_and_finishes_at_l2_without_a_target(self):
        store.set_target(self.ws, None)
        pid = self.add()
        store.request_depth(self.ws, pid, 'L2', 'Explain this method and its limitations.')
        self.attach(pid)
        handoff = self.l2(pid)
        del handoff['assessment']
        handoff['targeted']['focus'][0]['question_ids'] = []
        handoff['decision'] = decision('REMAIN_AT_L2', by='AGENT_JUDGMENT', refs=('S-COORD',))
        status = store.submit(self.ws, handoff)
        self.assertEqual(status['next_action']['kind'], 'NONE')
        self.assertEqual(status['target_dependent']['focus_applicability']['F1']['state'], 'CURRENT')
        self.assertEqual([r['depth'] for r in self.record(pid)['passes']], ['L2'])
        self.assertIsNone(store.load_corpus(self.ws)['research_target'])
        self.assertEqual(status['independent_review'], 'NONE')

    def test_high_utility_is_not_a_mandate_and_an_unknown_can_remain(self):
        pid = self.add()
        store.request_depth(self.ws, pid, 'L1', 'Is it worth reading?')
        self.attach(pid)
        skim = self.l1(pid, decision('PROMOTE_TO_L2', refs=('S-METHOD',), focus=['Coordination protocol']),
                       topic_relevance='HIGH', research_utility='HIGH', evidence_adequacy='UNKNOWN')
        skim['card'] = {k: skim['card'][k] for k in ['research_problem', 'core_method']}
        store.submit(self.ws, skim)
        self.assertEqual(store.recommend(self.ws, pid)['anticipated_depth'], 'L2')
        store.route(self.ws, pid, decision('PROMOTE_TO_L3', by='AGENT_JUDGMENT', refs=('S-METHOD',)))
        self.assertEqual(store.status(self.ws, pid)['next_action']['kind'], 'UPGRADE_NEEDS_USER')
        self.expect('UPGRADE_NOT_AUTHORIZED', triage.upgrade_trigger, self.record(pid), 'L3', TARGET)
        store.request_depth(self.ws, pid, 'L3', 'Independently verify the whole paper.')
        self.assertEqual(triage.upgrade_trigger(self.record(pid), 'L3', TARGET)['kind'], 'USER_REQUEST')

    def test_scoped_use_and_independent_check_do_not_grant_paper_acceptance(self):
        pid = self.skimmed(methodological_relevance='MEDIUM', research_utility='MEDIUM')
        store.submit(self.ws, self.l2(pid))
        before = self.record(pid)
        assertion = {'synthesis_claim_id': 'S', 'writer_id': 'synthesizer', 'text': 'This design replans on failure.',
                     'evidence_basis': 'SCOPED_L2', 'use_kind': 'METHOD', 'strength': 'CANDIDATE',
                     'limitation': 'Described design in section 3.2 only; no isolated effect measured.',
                     'support': [{'paper_id': pid, 'local_claim_id': 'LC1', 'attribution': 'REPORTED_OBSERVATION',
                                  'source_sha256': before['full_text']['current_sha256'], 'evidence_state': 'SUPPORTED',
                                  'checks': {'context': 'Section 3.2 concerns executor failures.', 'mechanism': 'A failure triggers replanning.'}}]}
        check = lambda: store.check_synthesis(self.ws, [assertion])
        self.assertTrue(check()['valid'])
        assertion['use_kind'] = 'COMPARISON'
        self.assertFalse(check()['valid'])
        assertion['use_kind'] = 'MECHANISM_EFFECT'
        assertion['support'][0]['checks'].update(result='failure count', metric='count', baseline='standard', conditions='one setup')
        self.assertFalse(check()['valid'])  # no isolating control
        assertion.update(use_kind='METHOD', strength='CONCLUSION')
        missing = check()
        self.assertFalse(missing['valid'])
        binding = missing['claims'][0]['scoped_uses'][0]['binding_sha256']
        receipt = {'kind': 'SCOPED_CLAIM_REVIEW', 'decision': 'SUPPORTS_WITHIN_SCOPE', 'binding_sha256': binding,
                   'reviewer_id': 'reader', 'independence_disclosure': 'Separate from all writers.',
                   'source_observation': 'The failure branch in 3.2 returns to the planner.', 'limits': 'Design only.'}
        ref = 'scoped_reviews/s.json'
        assertion['support'][0]['review_ref'] = ref
        path = store.paper_dir(self.ws, pid)/ref
        write(path, receipt)
        self.assertFalse(check()['valid'])  # reader authored the L2 pass
        write(path, dict(receipt, reviewer_id='distinct'))
        self.assertTrue(check()['valid'])
        self.assertEqual(check()['claims'][0]['scoped_uses'][0]['review_status'], 'INDEPENDENTLY_CHECKED_FOR_THIS_USE')
        self.assertEqual(self.record(pid), before)
        assertion['text'] += ' It lowers failures.'
        self.assertFalse(check()['valid'])
        assertion['evidence_basis'] = 'ACCEPTED'
        self.assertFalse(check()['valid'])
        assertion['evidence_basis'] = 'SCOPED_L2'
        store.set_target(self.ws, {**copy.deepcopy(TARGET), 'revision': 2, 'purpose': 'Another research question'})
        self.assertFalse(check()['valid'])

    def test_budget_counts_reader_upgrades_and_separates_review_rounds(self):
        for i in range(20):
            usage.log_usage(self.ws, 'MODEL_CALL', 'P0001', 'L1' if i < 6 else 'L2')
        for rnd, output in [(1, 3000), (2, 8000)]:
            usage.log_usage(self.ws, 'REVIEWER_CALL', 'P0001', 'L3', review_round=rnd, tokens_out=output, measured_by='fixture')
        owner, first, delta = usage.summary(self.ws, 'P0001')['budget_windows']
        self.assertEqual((owner['depth'], owner['responses_reported'], owner['output_reported'], owner['soft_alert']), ('L2', 20, None, True))
        self.assertEqual((first['review_round'], first['soft_alert'], delta['review_round'], delta['soft_alert']), (1, False, 2, True))
