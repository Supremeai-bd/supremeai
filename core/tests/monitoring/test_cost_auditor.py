from tools.billing.cost_auditor import CostAuditor


class TestCostAuditor:
    def test_init(self):
        auditor = CostAuditor()
        assert auditor is not None

    def test_generate_report_no_history(self):
        # বাংলা মন্তব্য: টাস্ক হিস্ট্রি খালি থাকলে generate_report() এরর রিটার্ন করে কিনা তা পরীক্ষা করা হচ্ছে।
        auditor = CostAuditor()
        res = auditor.generate_report()
        assert "error" in res
