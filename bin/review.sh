#!/bin/bash
zgrep -l fixme "$HOME/$1/tasks/"*.osm.gz | rev | cut -d"/" -f1 | rev  2>/dev/null
