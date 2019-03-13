#!/bin/bash

set -e

GOPATH=$PWD
cd src/github.com/alexander-matz/news3k
go get github.com/mattn/go-sqlite3
go build -o news3k-web
