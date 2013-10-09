# This file is part of release-path
#
#Copyright (c) 2012 Wireless Generation, Inc.
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

import re
import logging
from git import GitCommandError
from simpleversions import Version


class BranchAlreadyExists(Exception):
    def __init__(self, branch_name):
        Exception.__init__(self, "Branch %s already exists" % branch_name)


class InvalidSubmoduleBranch(Exception):
    def __init__(self, branch_name):
        Exception.__init__(
            self,
            'Submodules are in a suboptimal state for branch %s' % branch_name)


VERSION = r'\d+([.,]\d+)'
SUBVERSION = r'[-~_]%s' % VERSION


def branch_pattern(prefix='release_', suffix=''):
    return r'%s%s(%s)*%s' % (prefix, VERSION, SUBVERSION, suffix)


def release_branches(repo, remote='origin',
                     branch_prefix='release_', branch_suffix=''):
    for branch in repo.git.branch('-r').split('\n'):
        branch = branch.strip()
        branch_remote, _, branch_name = branch.partition('/')
        if branch_remote != remote:
            continue

        if not re.match(branch_pattern(branch_prefix, branch_suffix),
                        branch_name):
            continue

        yield branch_name


def create_release_branch(repo, version, remote='origin',
                          branch_prefix='release_', branch_suffix=''):
    new_branch = Version(branch_prefix + version + branch_suffix)
    branch_point = None

    repo.git.fetch()

    for branch_name in release_branches(repo, remote, branch_prefix,
                                        branch_suffix):
        branch = Version(branch_name)

        if branch <= new_branch:
            if branch_point is None or branch > branch_point:
                branch_point = branch

    if branch_point is None:
        raise Exception(
            'No release branch earlier than %s found to branch from' %
            new_branch)

    if branch_point == new_branch:
        raise BranchAlreadyExists(branch_point)

    remote_old_branch = '/'.join((remote, str(branch_point)))
    repo.git.branch(str(new_branch), remote_old_branch)
    repo.git.submodule('foreach',
                       'git branch %s %s' % (new_branch, remote_old_branch))

    return str(branch_point), str(new_branch)


def merge_branches(repo, branches, remote='origin', push=True, fetch=True):
    verified = {}
    for branch in branches:
        try:
            verify_submodule_branch_structure(repo, branch, fetch)
            verified[branch] = True
        except InvalidSubmoduleBranch:
            verified[branch] = False

    failed_merges = []
    for from_branch, to_branch in zip(branches, branches[1:]):
        if not verified[from_branch]:
            logging.error('Unable to merge from branch %s due to invalid '
                          'submodule branch' % from_branch)
            failed_merges.append((from_branch, to_branch))
            continue

        if not verified[to_branch]:
            logging.error('Unable to merge to branch %s due to invalid '
                          'submodule branch' % to_branch)
            failed_merges.append((from_branch, to_branch))
            continue

        try:
            logging.info('Merging %s into %s' % (from_branch, to_branch))
            deep_merge(repo, from_branch, to_branch, remote)
            if push:
                repo.git.push(remote, to_branch)

        except GitCommandError as exc:
            logging.exception('Failed to merge %s into %s\nStderr:\n%s' %
                              (from_branch, to_branch, exc.stderr))
            failed_merges.append((from_branch, to_branch))

    return failed_merges


def no_ff_deep_merge(repo, from_branch, to_branch, remote='origin'):
    """
    Merge from_branch into to_branch, while also merge from_branch into
    to_branch in each of the submodules of this repository
    """

    remote_from_branch = "%s/%s" % (remote, from_branch)
    remote_to_branch = "%s/%s" % (remote, to_branch)

    # Prepare to merge to to_branch by clearing out any local changes
    repo.git.reset('--hard', 'HEAD')
    repo.git.checkout('-f', to_branch)
    repo.git.reset('--hard', remote_to_branch)

    # If there have been no commits on from_branch that aren't on to_branch,
    # then we don't need to merge at all
    if not repo.git.log(remote_from_branch, "^%s" % remote_to_branch,
                        '--oneline'):
        return

    try:
        # Merge from from_branch, but leave the commit open to include
        # the submodule merges. Even if the merge is in conflict,
        # don't stop
        repo.git.merge('--no-commit', remote_from_branch,
                       with_exceptions=False)

        # Prepare submodules for merge to to_branch. Assumes that
        # submodule branch structure has been verified by
        # verify_submodule_branch_structure
        repo.git.submodule('foreach', "git checkout -f %s" % to_branch)
        repo.git.submodule('foreach', "git reset --hard %s" % remote_to_branch)

        repo.git.submodule('foreach', "git merge %s" % remote_from_branch)
        # If there are any changes recorded, then commit
        if repo.git.status('-s') != []:
            for path in submodule_status(repo).keys():
                repo.git.add(path)
            repo.git.commit(
                '-m', "deep merged %s to %s" % (from_branch, to_branch),
                '--allow-empty')

        # Push all changes (this is a no-op if there are no changes)
        repo.git.submodule('foreach', "git push origin %s" % to_branch)
        repo.git.push('origin', to_branch)
    except:
        # Merge failed, reset the repo
        repo.git.reset('--hard', 'HEAD')
        repo.git.submodule('foreach', "git reset --hard HEAD")
        raise


def fast_forward_deep_merge(repo, from_branch, to_branch, remote='origin'):
    """
    Do a fast-forward merge of the supermodule and submodules
    """
    remote_from_branch = "%s/%s" % (remote, from_branch)
    remote_to_branch = "%s/%s" % (remote, to_branch)

    # Prep the supermodule
    repo.git.checkout('-f', to_branch)
    repo.git.reset('--hard', remote_to_branch)

    # FF merge the supermodule
    repo.git.merge('--ff-only', remote_from_branch)

    # Prep the submodules
    repo.git.submodule('foreach', 'git checkout -f ' + to_branch)
    repo.git.submodule('foreach', 'git reset --hard ' + remote_to_branch)

    # FF merge the submodules
    repo.git.submodule('foreach', 'git merge --ff-only ' + remote_from_branch)

    # Push all the changes
    repo.git.submodule('foreach', 'git push origin ' + to_branch)
    repo.git.push('origin', to_branch)


def deep_merge(repo, from_branch, to_branch, remote='origin'):
    """
    Do a fast-forward deep merge from `from_branch` to `to_branch` if
    possible, otherwise do a regular deep merge.
    """
    # If there are no commits in from_branch that are not in to_branch
    # then we can do a fast forward merge
    if repo.git.log('%s/%s..%s/%s' % (remote, from_branch,
                                      remote, to_branch)) == []:
        fast_forward_deep_merge(repo, from_branch, to_branch)
    else:
        no_ff_deep_merge(repo, from_branch, to_branch)


def submodule_status(repo):
    submodules = {}
    for status in repo.git.submodule('status').split('\n'):
        if status == '':
            continue
        up_to_date = status[0]
        commit_hash = status[1:40]
        path, _, branch_id = status[42:].partition(' ')
        submodules[path] = (up_to_date, commit_hash, branch_id)
    return submodules


def verify_submodule_branch_structure(repo, branch_name, fetch=True,
                                      remote='origin'):
    """
    Throws an exception unless the commit at the tip of branch_name
    in the supermodule points to the tip of branch_name in each of
    the submodules
    """
    remote_branch = '/'.join([remote, branch_name])

    repo.git.reset('--hard', 'HEAD')
    repo.git.checkout('-f', branch_name)
    repo.git.reset('--hard', remote_branch)
    if fetch:
        repo.git.submodule('update', '--init')
        repo.git.submodule('foreach', 'git fetch')
    else:
        repo.git.submodule('update', '--init', '--no-fetch')
    try:
        repo.git.submodule('foreach', "git diff --quiet %s" % remote_branch)
    except GitCommandError:
        raise InvalidSubmoduleBranch(branch_name)
