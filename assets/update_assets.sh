#!/bin/bash

cd "$( dirname $0 )"

dest="../massmailer/static/massmailer/vendor/"
mkdir -p "$dest"

npm install

cp \
    node_modules/ace-builds/src-min-noconflict/ace.js \
    node_modules/ace-builds/src-min-noconflict/ext-themelist.js \
    node_modules/ace-builds/src-min-noconflict/ext-language_tools.js \
    node_modules/ace-builds/src-min-noconflict/mode-django.js \
    node_modules/select2/dist/css/select2.min.css \
    node_modules/select2/dist/js/select2.min.js \
    node_modules/bootstrap/dist/css/bootstrap.min.css \
    node_modules/bootstrap/dist/js/bootstrap.min.js \
    node_modules/font-awesome/css/font-awesome.min.css \
    "$dest"
