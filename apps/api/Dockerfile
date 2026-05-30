# syntax=docker/dockerfile:1.7

FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /app

ARG MAVEN_MIRROR_URL
ARG MAVEN_BUILD_OPTS="-DskipTests package"

COPY pom.xml ./

RUN --mount=type=cache,target=/root/.m2 \
    if [ -n "$MAVEN_MIRROR_URL" ]; then \
      printf '%s\n' \
        '<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"' \
        '          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' \
        '          xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0 https://maven.apache.org/xsd/settings-1.0.0.xsd">' \
        '  <mirrors>' \
        '    <mirror>' \
        '      <id>custom-mirror</id>' \
        '      <name>custom-mirror</name>' \
        "      <url>${MAVEN_MIRROR_URL}</url>" \
        '      <mirrorOf>*</mirrorOf>' \
        '    </mirror>' \
        '  </mirrors>' \
        '</settings>' >/tmp/settings.xml; \
      mvn -B -q -s /tmp/settings.xml dependency:go-offline; \
    else \
      mvn -B -q dependency:go-offline; \
    fi

COPY src ./src

RUN --mount=type=cache,target=/root/.m2 \
    if [ -n "$MAVEN_MIRROR_URL" ]; then \
      mvn -B -q -s /tmp/settings.xml ${MAVEN_BUILD_OPTS}; \
    else \
      mvn -B -q ${MAVEN_BUILD_OPTS}; \
    fi

FROM eclipse-temurin:21-jre
WORKDIR /app

COPY --from=build /app/target/*.jar /app/app.jar

EXPOSE 8092

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
