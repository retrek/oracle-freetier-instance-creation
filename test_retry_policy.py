import unittest
from unittest.mock import patch

from retry_policy import retry_delay


class RetryPolicyTests(unittest.TestCase):
    @patch("retry_policy.random.uniform", side_effect=lambda low, high: low)
    def test_throttling_retains_slower_rate_after_capacity_miss(self, _):
        interval, delay = retry_delay({"status": 429}, 60)
        self.assertEqual((interval, delay), (120, 120))
        self.assertEqual(retry_delay({"code": "InternalError"}, interval), (120, 120))
        self.assertEqual(retry_delay({"code": "TooManyRequests"}, interval), (240, 240))

    @patch("retry_policy.random.uniform", side_effect=lambda low, high: low)
    def test_cap_and_configured_longer_interval(self, _):
        self.assertEqual(retry_delay({"status": 429}, 800), (900, 900))
        self.assertEqual(retry_delay({"status": 429}, 1800), (1800, 1800))
        self.assertEqual(retry_delay({}, 0), (60, 60))

    def test_jitter_never_retries_before_interval(self):
        for _ in range(100):
            interval, delay = retry_delay({}, 120)
            self.assertEqual(interval, 120)
            self.assertGreaterEqual(delay, 120)
            self.assertLessEqual(delay, 150)

    @patch("retry_policy.random.uniform", return_value=120)
    def test_retry_after(self, _):
        self.assertEqual(retry_delay({"status": 429, "retry_after": "600"}, 60), (120, 600))
        for value in ("invalid", "inf", "nan", "-100"):
            self.assertEqual(retry_delay({"retry_after": value}, 120), (120, 120))
        self.assertEqual(retry_delay({"retry_after": "Mon, 26 Oct 2099 00:00:00 GMT"}, 120)[0], 120)
        self.assertGreater(retry_delay({"retry_after": "Mon, 26 Oct 2099 00:00:00 GMT"}, 120)[1], 600)


if __name__ == "__main__":
    unittest.main()
