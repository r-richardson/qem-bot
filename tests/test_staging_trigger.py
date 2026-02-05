# Copyright SUSE LLC
# SPDX-License-Identifier: MIT
import logging
from argparse import Namespace
from urllib.parse import urlparse

import pytest
from pytest_mock import MockerFixture
import responses
from responses import GET

from openqabot.giteasync import GiteaSync
from openqabot.loader.gitea import make_submission_from_gitea_pr

@pytest.fixture
def staging_pr():
    return {
        "number": 2068,
        "state": "open",
        "url": "https://src.suse.de/products/SLFO/pulls/2068",
        "base": {"repo": {"name": "SLFO", "full_name": "products/SLFO"}},
        "labels": [{"name": "staging/In Progress"}],
    }

def test_make_submission_extracts_labels(mocker: MockerFixture, staging_pr):
    mocker.patch("openqabot.loader.gitea.get_json", return_value=[]) # reviews
    mocker.patch("openqabot.loader.gitea.add_reviews", return_value=0)
    mocker.patch("openqabot.loader.gitea.add_comments_and_referenced_build_results")
    mocker.patch("openqabot.loader.gitea.add_packages_from_files")

    # We need to ensure it doesn't return None due to missing channels/packages
    # but here we just want to check if labels are extracted

    submission = make_submission_from_gitea_pr(
        staging_pr,
        token={},
        only_successful_builds=False,
        only_requested_prs=True,
        dry=True
    )

    # Even if it returns None (because of missing packages/channels in mock),
    # we can test the logic by inspecting how it was called or by making it return a dict.
    # Let's mock more to get a real dict back.

    def mock_add_comments(sub, comments, dry):
        sub["channels"] = ["SUSE:SLFO:Main:PullRequest:2068:SLES:x86_64"]

    mocker.patch("openqabot.loader.gitea.add_comments_and_referenced_build_results", side_effect=mock_add_comments)

    def mock_add_packages(sub, token, files, dry):
        sub["packages"] = ["test-package"]

    mocker.patch("openqabot.loader.gitea.add_packages_from_files", side_effect=mock_add_packages)

    submission = make_submission_from_gitea_pr(
        staging_pr,
        token={},
        only_successful_builds=False,
        only_requested_prs=True,
        dry=True
    )

    assert submission is not None
    assert "staging/In Progress" in submission["labels"]
    # Verify it was NOT skipped despite having 0 QAM reviews (because of is_staging logic)
    assert submission["number"] == 2068

@responses.activate
def test_giteasync_triggers_jobs(mocker: MockerFixture, caplog: pytest.LogCaptureFixture, staging_pr):
    caplog.set_level(logging.INFO)

    args = Namespace(
        dry=False,
        fake_data=True, # Use fake data to avoid real network requests for ISOs
        token="123",
        gitea_token="456",
        retry=0,
        gitea_repo="products/SLFO",
        allow_build_failures=True,
        consider_unrequested_prs=False,
        pr_number=2068,
        staging_label="staging/In Progress",
        openqa_instance=urlparse("https://openqa.suse.de"),
    )

    responses.add(GET, "https://src.suse.de/api/v1/repos/products/SLFO/pulls/2068", json=staging_pr)

    submission = {
        "number": 2068,
        "project": "products/SLFO",
        "repo_name": "products/SLFO",
        "labels": ["staging/In Progress"],
        "channels": ["SUSE:SLFO:Main:PullRequest:2068:SLES:x86_64"],
    }
    mocker.patch("openqabot.giteasync.get_submissions_from_open_prs", return_value=[submission])

    mock_post = mocker.patch("openqabot.openqa.OpenQAInterface.post_job", return_value={"ids": [12345]})

    mock_post_json = mocker.patch("openqabot.giteasync.post_json")

    sync = GiteaSync(args)
    sync()

    assert "Triggering staging tests for PR 2068" in caplog.text
    assert mock_post.called
    settings = mock_post.call_args[0][0]
    assert settings["ARCH"] == "x86_64"
    assert settings["VERSION"] == "16.1"
    assert "PR-2068" in settings["BUILD"]
    assert settings["_GITEA_PR"] == "2068"

    assert mock_post_json.called
    comment_args = mock_post_json.call_args
    assert "repos/products/SLFO/issues/2068/comments" in comment_args[0][0]
    assert "Scheduled openQA staging test for x86_64" in comment_args[0][2]["body"]
    assert "tests/12345" in comment_args[0][2]["body"]
    assert "tests/12345/badge" in comment_args[0][2]["body"]
