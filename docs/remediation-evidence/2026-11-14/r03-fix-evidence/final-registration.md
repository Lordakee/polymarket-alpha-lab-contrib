R03-fix final registration (steps 1-3 of the release sequence)
reviewed-A=8c01798cedf60b7f04346f5d12f6471953db8b28
distribution-fix=7d993df58574c0cb713d360334fe352ed591c4a9
base-main=ad001c77a530c156b6ce42ff21b01b8711fd3e2b
merge-M=29a86f642adb6df83c81a2bfff4f18ddd906ef62 (parents ad001c77a530c156b6ce42ff21b01b8711fd3e2b + 7d993df58574c0cb713d360334fe352ed591c4a9, --no-ff, identity ZCode <zcode@local>)
replay: git checkout -b r03-fix-final ad001c77a530c156b6ce42ff21b01b8711fd3e2b && git merge --no-ff 7d993df58574c0cb713d360334fe352ed591c4a9 && git cherry-pick 8c01798cedf60b7f04346f5d12f6471953db8b28
final-B=f5ca185a50ad6349275cd79dabd5b701b65a2548 tree=b9c40393a2e2b9f3ad217b9f01545c7788a89b14
tree-verification: version-switch blob matches A (f4441272712333b0bee29554a9644a1a0056b3f3); each distribution file blob matches 7d993df58574c0cb713d360334fe352ed591c4a9; diff A..B == the 3 distribution files; diff M..B == tests/test_project_postgres_version_switch_native.py; diff base..B == 4 files; worktree clean
re-verify: focused 74 passed / 1 skipped / 0 failed; compile PASS (109348 bytes); diff --check clean on base..M, M..B, base..B
code review: fresh reviewer PASS, 0 P1/P2; P3-1 manifest field corrected here (see correction_note in secret-scan-manifest.json); P3-2 fail-message wording deviation recorded, no change required
not-pushed: B awaits the coordinator release agent; A != B registered
