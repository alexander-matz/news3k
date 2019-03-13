#!/bin/bash

set -e

GOPATH=$PWD
BASE=src/github.com/alexander-matz/news3k
set -x
$BASE/news3k-web --static=$BASE/static --templates=$BASE/templates $@
