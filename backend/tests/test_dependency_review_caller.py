"""Keep Naruon's central dependency-review caller pinned and blocking."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
REVIEWED_SUPPLIER_SHA = '58d12a9f1b46d611f75cfcf3e6c5a3fe19a55f96'


class DependencyReviewCallerContract(unittest.TestCase):
    """Reject hosted duplication and weakened dependency policy."""

    def test_calls_pinned_central_supplier_with_blocking_policy(self) -> None:
        """Keep trigger, permissions, concurrency and all four supplier inputs."""
        text = (ROOT / '.github/workflows/dependency-review.yml').read_text()
        self.assertRegex(
            text,
            r'uses: ContextualWisdomLab/\.github/\.github/workflows/'
            r'dependency-review\.yml@[0-9a-f]{40}\b',
        )
        pin = re.search(r'dependency-review\.yml@([0-9a-f]{40})', text)
        self.assertIsNotNone(pin)
        self.assertEqual(pin.group(1), REVIEWED_SUPPLIER_SHA)
        self.assertIn(
            f'dependency-review.yml@{REVIEWED_SUPPLIER_SHA} '
            '# v5.0.0 dependency-review-action supplier', text,
        )
        for expected in (
            'pull_request:', '- develop', '- master', '- "release/**"',
            'workflow_dispatch:', 'contents: read', 'pull-requests: read',
            'group: dependency-review-${{ github.event.pull_request.number || github.ref }}',
            'cancel-in-progress: true', 'fail_on_severity: moderate',
            'allow_ghsas: ""', 'continue_on_error: false',
            'comment_summary_in_pr: never',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)
        self.assertNotIn('runs-on:', text)
        self.assertNotIn('steps:', text)
        self.assertNotIn('secrets:', text)
        self.assertNotIn('continue-on-error: true', text)


if __name__ == '__main__':
    unittest.main()
