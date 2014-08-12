#!/usr/bin/python

# This file is part of release-path
#
#Copyright (c) 2014 Amplify Education
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

import sys
import logging
import re
from argparse import ArgumentParser
from ConfigParser import SafeConfigParser

from git import Repo, GitCommandError
from release_path import deep_merge

PRODUCT_NAMESPACE="product"
DEPLOY_NAMESPACE="deploy"
DEFAULT_REMOTE="origin"
DEFAULT_CONFIG="upstream_merge.conf"

class BRANCH_TYPE(object):
    PRODUCTION = "production"
    PREPROD = "preprod"
    CQA = "current"
    FQA = "future"
    _merge_order = [PRODUCTION, PREPROD, CQA, FQA]
    _branch_pattern = re.compile("/([-\w+]+)$")
    ANY_TYPE = "(?:" +  "|".join(_merge_order) + ")"

    @staticmethod
    def merge_to(merge_from):
        merge_order = BRANCH_TYPE._merge_order
        if merge_from not in merge_order:
            raise Exception("Branch type %s is not recognized" % (merge_from))
        from_idx = merge_order.index(merge_from)
        if from_idx == len(merge_order) - 1:
            return None
        return merge_order[from_idx + 1]

    @staticmethod
    def branch_type(branch_name):
        match = re.search(BRANCH_TYPE._branch_pattern, branch_name)
        if match:
            foundtype = match.group(1)
            if foundtype in BRANCH_TYPE._merge_order:
                return foundtype
        return None

    @staticmethod
    def upstream_branches(branchtype):
        start_point = BRANCH_TYPE._merge_order.index(branchtype) + 1
        return BRANCH_TYPE._merge_order[start_point::]

class IllegalCommitException(Exception):
    # empty definition
    pass
class InvalidBranchException(Exception):
    # empty definition
    pass

def main():
    (args, config, repo) = init_script()
    logging.error("Argument-parsing yields %s" % args)
    return 0

def find_product_emails(config, failed_branches, fallback_email):
    emails=set()
    matcher = re.compile("%s/([-\w]+)/%s" % (PRODUCT_NAMESPACE, BRANCH_TYPE.ANY_TYPE))
    for failed in failed_branches:
        match = re.match(matcher,failed[0])
        product_name = match.group(1)
        if config.has_option("project email",product_name):
            product_email = config.get("project email", product_name)
            emails.add(product_email)
            logging.debug("Found e-mail %s for project %s" % (product_email, product_name))
        else:
            emails.add(fallback_email)
            logging.debug("No e-mail found for project %s: falling back to %s" % (product_name, fallback_email))
    return emails

def save_failure_info(failed_branches, config, email_filename, project_filename):
    project_list = ", ".join([ fail[0] for fail in failed_branches])
    logging.info("Failed merges to the following products: %s" % project_list)
    fallback_email = config.get("global","fallback_address")
    logging.debug("Fallback e-mail found: "+ fallback_email)
    emails = find_product_emails(config, failed_branches, fallback_email)
    email_list = ",".join(emails)
    logging.debug("Found the following emails: %s" % email_list)

    addr_file = open(email_filename,"w")
    addr_file.write(email_list)
    addr_file.close()

    content_file = open(project_filename, "w")
    content_file.write(project_list)
    content_file.close()

def init_script():
    args = parse_args()
    logging.basicConfig(level=args.log_level)
    logging.debug("Script arguments: %s" % args)
    config = SafeConfigParser()
    if not config.read(args.config_file):
        raise Exception("Configuration file %s was not read" % (args.config_file))
    return (args, config, Repo())

def find_branches(args, repo):
    source_branch = args.source_branch
    source_type = args.source_branch_type
    dest_branch = args.destination_branch
    dest_type = None
    logging.debug("From arguments, source branch is '%s', source type is '%s' and destination branch is %s"
                  % (source_branch, source_type, dest_branch))
    if source_branch is None:
        if source_type is None:
            raise Exception("either --source-type or --source-branch must be specified")
        source_branch = find_deploy_branch(repo, remote=args.remote, branchtype=source_type)

    if source_type is None:
        source_type = find_branch_type(source_branch)
    if source_type:
        dest_type = BRANCH_TYPE.merge_to(source_type)
    if dest_branch is None:
        if dest_type is None:
            raise Exception("Unable to infer destination branch, and none provided")
        dest_branch = find_deploy_branch(repo, remote=args.remote, branchtype=dest_type)
    if dest_type:
        extra_branches = find_product_branches(repo, remote=args.remote, branchtype=dest_type)
    else:
        extra_branches = None
    branch_tuple = (source_branch, dest_branch, extra_branches)
    logging.debug("Final source branch is '%s'; destination is '%s'; other branches %s" % branch_tuple)
    return branch_tuple

def find_branch_type(branch):
    """
    Find the type (production/preprod/current/future) of a given branch
    """
    # this is kind of silly-looking, but avoids exposing BRANCH_
    return BRANCH_TYPE.branch_type(branch)

def parse_args():
    parser = ArgumentParser()
    parser.add_argument("-t", "--source-type", action="store", dest="source_branch_type",
                        help="Type of the branch being merged from: production, preprod, current or future")
    parser.add_argument("-r", "--remote", action="store", dest="remote", default=DEFAULT_REMOTE,
                        help="Name of the git remote to use (defaults to '%s')" % DEFAULT_REMOTE)
    parser.add_argument("-v","--verbose", action="store_const", dest="log_level",const=logging.DEBUG, default=logging.INFO,
                        help="Output debugging messages to STDOUT")
    parser.add_argument("-q","--quiet", action="store_const", dest="log_level",const=logging.FATAL,
                        help="Output only FATAL and non-optional messages to STDOUT")
    parser.add_argument("-c","--config",action="store", dest="config_file", default=DEFAULT_CONFIG,
                        help="Configuration file to parse (defaults to '%s')" % DEFAULT_CONFIG)
    parser.add_argument("-s", "--source-branch", action="store", dest="source_branch",
                        help="Branch being read (will remain unmodified)")
    parser.add_argument("-d", "--dest-branch", action="store", dest="destination_branch",
                        help="Branch to be merged into")
    return parser.parse_args()

def find_deploy_branch(repo, remote=DEFAULT_REMOTE, branchtype=BRANCH_TYPE.PRODUCTION):
    deploy_branch = find_remote_branches(repo, pattern= "deploy/%s" % (branchtype))
    if 1 != len(deploy_branch):
        raise Exception("Should have found exactly one branch matching %s, but found %s" % (branchtype, len(deploy_branch)))
    return deploy_branch[0]

def find_product_branches(repo, remote=DEFAULT_REMOTE, branchtype=BRANCH_TYPE.PREPROD):
    product_branches = find_remote_branches(repo, pattern="%s/*/%s" % (PRODUCT_NAMESPACE, branchtype))
    if not product_branches:
        raise Exception("No product branches of type '%s' found" % (branchtype))
    return product_branches

def find_upstream_branch(repo, source_branch, remote=DEFAULT_REMOTE):
    logging.debug("Seeking upstream branch for %s" % source_branch)
    source_type = find_branch_type(source_branch)
    if source_type is None:
        raise InvalidBranchException("Couldn't determine type for branch " + source_branch)
    dest_type = BRANCH_TYPE.merge_to(source_type)
    if not dest_type:
        return None
    dest_branch_candidate = re.sub( source_type + "$", dest_type, source_branch)
    
    found_branches = find_remote_branches(repo, remote=remote, pattern=dest_branch_candidate)
    logging.debug("Seeking upstream branch matching %s, found %s"
                  % (dest_branch_candidate, found_branches))
    if 1 == len(found_branches):
        return found_branches[0]
    elif 1 < len(found_branches):
        logging.error("Found unexpectedly large number of branches: %s"
                      % found_branches)
        raise Exception("Expected at most one branch matching %s, but found %s"
                        % (dest_branch_candidate, found_branches))
    else:
        return None

def find_remote_branches(repo, remote=DEFAULT_REMOTE,pattern=None):
    remote_prefix = "refs/remotes/%s/" % (remote)
    if pattern is None: # one-line version of this block is not python2.4 compatible
        search_pattern = remote_prefix
    else:
        search_pattern = remote_prefix + pattern
    command_output = repo.git.for_each_ref(search_pattern, "--format=%(refname)");
    if command_output:
        raw_branches = command_output.split("\n")
        logging.debug("for-each-ref returned %s lines" % (len(raw_branches)))
        return [ branch.replace(remote_prefix,"") for branch in raw_branches]
    else:
        logging.debug("for-each-ref output is empty")
        return []

def check_guard_commits(repo, config, branchtype):
    # loop over upstream branch types, checking for guards for any of them:
    for upstream in BRANCH_TYPE.upstream_branches(branchtype):
        if not config.has_option("guard commits", upstream):
            logging.debug("No guard commit found for %s" % upstream)
            continue
        guard = config.get("guard commits", upstream)
        logging.debug("Found guard commit %s protecting merges from %s" % (guard, upstream))
        merge_base = repo.git.merge_base("HEAD",guard)
        if merge_base == guard:
            raise IllegalCommitException("Found guard commit %s (guard for %s): cannot merge this into a %s branch" % (guard, upstream, branchtype))

if __name__ == "__main__":
    sys.exit(main())
