#!/usr/bin/env bash
set -euo pipefail

export JAVA_HOME="/home/ubuntu/.local/tools/jdk-21"
export MAVEN_HOME="/home/ubuntu/.local/tools/apache-maven-3.9.16"
export NODE_HOME="/home/ubuntu/.local/tools/node-v22.22.3-linux-x64"
export PATH="$JAVA_HOME/bin:$MAVEN_HOME/bin:$NODE_HOME/bin:$PATH"

echo "JAVA_HOME=$JAVA_HOME"
echo "MAVEN_HOME=$MAVEN_HOME"
echo "NODE_HOME=$NODE_HOME"
