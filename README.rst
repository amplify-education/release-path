Release-path
------------

This library is designed to facilitate a particular release pattern,
using git branches.

The branching model relies on a 'next' branch where all changes are merged 
together to be tested on integration machines, and then a series of release
specific branches.

Change flow shown below::

    . |
    . |
    . |
    | |
    * | release 1.0
    |\|
    | * merge 1.0 to next for testing
    | |
    * | edit 1.0: a
    |\|
    | * merge 1.0a to next for testing
    | |
    * |  edit 1.0: b
    |\|
    | * merge 1.0ab to next for testing
    | \
    |  \
    |\  | 
    | * | branch for release 1.1
    | |\|
    | | * merge 1.1 to next for testing
    | | |
    * | | edit 1.0: c
    |\| |
    | * | merge c to 1.1
    | |\|
    | | * merge 1.1abc to next for testing
    | | |
    | * | edit 1.1: d
    | |\|
    | | * merge 1.1abcd to next for testing
    | | |
    * | | edit 1.0: e
    |\| |
    | * | merge e to 1.1
    | |\|
    | | * merge 1.1abcde to next for testing
    | | |
    | * | edit 1.1: f
    | |\|
    | | * merge 1.1abcdef to next for testing
    | | |
    * | | release 1.0.1
     \| |
      * | merge 1.0.1 to 1.1
      |\|
      | * merge 1.1 to next for testing
      | |

mk_release_branch
=================

This creates a new release branch, branched off the next smallest release branch
that already exists

deep_merge
==========

This merges two branches, and also merges the same branches in any submodules. This
is mainly used for repositories that use submodules for access control

merge_release_branches
======================

This merges changes downstream in releases (1.0 -> 1.1 -> 1.2 -> ... -> next). The
branches are merged in turn. If any merge fails, it's skipped, but the merges downstream
of it continue.

branches_pending_release
========================

This shows which branches have been merged to release branches, and which have only
been merged to next
