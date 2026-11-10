"""Exact manual release UX, immutable checkouts, and unchanged unrelated CI."""

import unittest
import re

from helper_support import ROOT, original
import yaml


class WorkflowTests(unittest.TestCase):
    def workflow(self, name):
        return yaml.safe_load((ROOT / ".github/workflows" / name).read_text())

    def test_exact_two_manual_release_entries_and_bump_choice(self):
        bump = self.workflow("bump-version.yml")
        build = self.workflow("release.yml")
        self.assertEqual(build["name"], "Build")
        self.assertEqual(build[True], {"workflow_dispatch": None})
        self.assertEqual(set(bump[True]), {"workflow_dispatch"})
        inputs = bump[True]["workflow_dispatch"]["inputs"]
        self.assertEqual(set(inputs), {"mode"})
        self.assertEqual(inputs["mode"]["type"], "choice")
        self.assertEqual(inputs["mode"]["options"], ["patch", "minor", "major"])
        self.assertEqual(inputs["mode"]["default"], "patch")
        self.assertIs(inputs["mode"]["required"], True)
        paths = {path.name for path in (ROOT / ".github/workflows").glob("*.yml")}
        self.assertEqual(paths, {"bump-version.yml", "release.yml", "ci.yml"})

    def test_all_checkout_refs_are_immutable_selected_event(self):
        count = 0
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            workflow = self.workflow(path.name)
            for job in workflow["jobs"].values():
                for step in job["steps"]:
                    if step.get("uses", "").startswith("actions/checkout@"):
                        self.assertEqual(step["with"]["ref"], "${{ github.sha }}")
                        count += 1
        self.assertEqual(count, 6)

    def test_native_ci_preserved_with_immutable_checkout_and_ownership_check(self):
        old = yaml.safe_load(original(".github/workflows/ci.yml"))
        for job in old["jobs"].values():
            for step in job["steps"]:
                if step.get("uses", "").startswith("actions/checkout@"):
                    step["with"] = {"ref": "${{ github.sha }}"}
        old["jobs"]["build-macos"]["steps"].insert(1, {
            "name": "check SDK string ownership",
            "run": "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover "
                   "-s tests -p test_string_ownership.py -v",
        })
        self.assertEqual(self.workflow("ci.yml"), old)

    def test_constant_cross_ref_publication_lock_without_invented_branch_gate(self):
        build = self.workflow("release.yml")
        group = build["concurrency"]["group"]
        self.assertIsInstance(group, str)
        self.assertNotIn("${{", group)
        self.assertIs(build["concurrency"]["cancel-in-progress"], False)
        for job in build["jobs"].values():
            self.assertNotIn("if", job)

    def test_bump_does_not_build_tag_release_dispatch_or_use_untrusted_expression_in_shell(self):
        bump = self.workflow("bump-version.yml")
        steps = bump["jobs"]["bump"]["steps"]
        for step in steps:
            script = step.get("run", "")
            for prohibited in ("git tag", "gh release", "gh workflow", "xcodebuild",
                               "msbuild", "workflow_dispatch", "${{ inputs."):
                self.assertNotIn(prohibited, script)
        self.assertIn("fetch-depth", steps[0]["with"])

    def test_build_uses_real_publication_cli_and_initial_not_final_preflight(self):
        commands = []
        for job in self.workflow("release.yml")["jobs"].values():
            for step in job["steps"]:
                script = step.get("run", "")
                if ".github/scripts/release.py" in script:
                    self.assertNotIn("--version", script)
                    commands.extend(re.findall(r"\.github/scripts/release\.py\s+(\w+)", script))
        self.assertEqual(commands.count("preflight"), 3)
        self.assertEqual(commands.count("publish"), 1)
        self.assertEqual(set(commands), {"preflight", "publish"})
