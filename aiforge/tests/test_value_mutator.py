from __future__ import annotations

import re
import unittest

from src.utils import reset_rng
from src.value_mutator import mutate_value


class ValueMutatorTest(unittest.TestCase):
    def test_mutates_month_name_date_to_valid_month_name_date(self) -> None:
        reset_rng(0)
        mutated = mutate_value("March 27, 1984", "B-ANSWER", seed=103)

        match = re.fullmatch(r"[A-Z][a-z]+ (\d{1,2}), (\d{4})", mutated)
        self.assertIsNotNone(match)
        day = int(match.group(1))
        self.assertGreaterEqual(day, 1)
        self.assertLessEqual(day, 31)

    def test_mutates_spaced_numeric_date_as_date_not_random_digits(self) -> None:
        reset_rng(0)
        mutated = mutate_value("9/ 3/ 92", "B-ANSWER", seed=7)

        self.assertRegex(mutated, r"^\d{1,2}/ \d{1,2}/ \d{2}$")

    def test_explicit_seed_controls_mutation_even_after_global_rng_reset(self) -> None:
        reset_rng(0)
        first = mutate_value("12.00", "total", seed=1)

        reset_rng(0)
        second = mutate_value("12.00", "total", seed=99)

        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
