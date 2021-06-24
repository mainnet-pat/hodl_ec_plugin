#!/bin/bash

pushd "$(dirname ${BASH_SOURCE[0]})"

rm hodl.v*.zip
rm -rf hodl/__pycache__
zip -r -X hodl.v1.0.0.zip hodl/ pictures/ diamond.png hodl.cash icons.* LICENSE manifest.json README.md

popd