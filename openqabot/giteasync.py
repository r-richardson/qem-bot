# Copyright SUSE LLC
# SPDX-License-Identifier: MIT
"""Sync Gitea pull requests to dashboard."""

from argparse import Namespace
from logging import getLogger
from pprint import pformat
from typing import Any

from .config import OBS_DOWNLOAD_URL, OPENQA_URL
from .loader.gitea import (
    comments_url,
    get_isos_from_obs,
    get_open_prs,
    get_submissions_from_open_prs,
    make_token_header,
    post_json,
)
from .loader.qem import update_submissions
from .utils import retry10 as retried_requests
from .openqa import OpenQAInterface

log = getLogger("bot.giteasync")


class GiteaSync:
    """Synchronization of Gitea PRs to dashboard."""

    def __init__(self, args: Namespace) -> None:
        """Initialize the GiteaSync class."""
        self.dry: bool = args.dry
        self.fake_data: bool = args.fake_data
        self.dashboard_token: dict[str, str] | None = (
            {"Authorization": "Token " + args.token} if args.token else None
        )
        self.gitea_token: dict[str, str] = make_token_header(args.gitea_token)
        self.open_prs: list[Any] = get_open_prs(
            self.gitea_token,
            args.gitea_repo,
            dry=self.fake_data,
            number=args.pr_number,
        )
        log.info(
            "Loaded %d active PRs from %s",
            len(self.open_prs),
            args.gitea_repo,
        )
        self.submissions = get_submissions_from_open_prs(
            self.open_prs,
            self.gitea_token,
            only_successful_builds=not args.allow_build_failures,
            only_requested_prs=not args.consider_unrequested_prs,
            dry=self.fake_data,
            staging_label=args.staging_label,
        )
        self.retry = args.retry
        self.openqa = OpenQAInterface(args)
        self.staging_label = args.staging_label

    def trigger_staging_jobs(self, submission: dict[str, Any]) -> None:
        pr_nr = submission["number"]
        log.info("Triggering staging tests for PR %s", pr_nr)

        for channel in submission.get("channels", []):
            parts = channel.split("#")[0].split(":")
            if len(parts) < 2:  # noqa: PLR2004
                continue

            arch = parts[-1]
            project = ":".join(parts[:-1])
            project_path = project.replace(":", ":/")
            iso_name, found_path = self._resolve_iso(project_path, arch, pr_nr)

            if not iso_name:
                log.warning("No ISO found for %s in %s", arch, project)
                continue

            iso_url = f"{OBS_DOWNLOAD_URL}/{project_path}/{found_path}/{iso_name}"
            settings = {
                "DISTRI": "sle",
                "VERSION": "16.1",
                "FLAVOR": "Online-Updates-Staging",
                "ARCH": arch,
                "ISO_URL": iso_url,
                "BUILD": f"PR-{pr_nr}-{iso_name}",
                "CASEDIR": "https://github.com/os-autoinst/os-autoinst-distri-opensuse.git",
                "_GITEA_PR": str(pr_nr),
            }

            if self.dry:
                log.info("Dry run: Would trigger openQA job with settings: %s", pformat(settings))
            else:
                try:
                    ret = self.openqa.post_job(settings)
                    log.info("Triggered openQA job for PR %s on %s", pr_nr, arch)
                    if ret and "ids" in ret:
                        for job_id in ret["ids"]:
                            job_url = f"https://{OPENQA_URL}/tests/{job_id}"
                            badge_url = f"{job_url}/badge"
                            comment = f"Scheduled openQA staging test for {arch}:\n\n[![Build Status]({badge_url})]({job_url})"
                            post_json(
                                comments_url(submission["repo_name"], pr_nr),
                                self.gitea_token,
                                {"body": comment},
                            )
                            log.info("Posted comment to PR %s: %s", pr_nr, job_url)
                except Exception as e:
                    log.error("Failed to trigger openQA job: %s", e)

    def _resolve_iso(self, project_path: str, arch: str, pr_nr: int) -> tuple[str | None, str | None]:
        if self.fake_data:
            return f"SLE-16.1-Staging-DVD-{arch}-Build{pr_nr}.iso", "iso"

        for path in ["iso", "product/iso"]:
            # Filter out Debug and Source ISOs, and prefer SLES or Staging if possible
            valid_isos = [
                name for name in get_isos_from_obs(project_path, path)
                if name.endswith(".iso") and arch in name
                and all(x not in name for x in ("-Debug", "-Source"))
            ]
            if valid_isos:
                iso_name = next((i for i in valid_isos if "SLES-16" in i or "SLE-16" in i), valid_isos[0])
                return iso_name, path
        return None, None

    def __call__(self) -> int:
        """Run the synchronization process."""
        data = self.submissions
        log.debug("Data for %d submissions: %s", len(data), pformat(data))

        for submission in data:
            if self.staging_label in submission.get("labels", []):
                self.trigger_staging_jobs(submission)

        if self.dry:
            log.info("Dry run: Would update QEM Dashboard data for %d submissions", len(data))
            return 0

        if self.dashboard_token:
            log.info("Syncing Gitea PRs to QEM Dashboard: Considering %d submissions", len(data))
            return update_submissions(
                self.dashboard_token, data, params={"type": "git"}, retry=self.retry
            )

        return 0
