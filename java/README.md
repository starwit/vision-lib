# vision-lib (Java)

Java edition of the [Starwit Awareness Engine](https://github.com/starwit/starwit-awareness-engine) (SAE) common components. See the [repository overview](../README.md) for the bigger picture. This package covers stream reading/writing and `.saedump` replay; the [Python package](../python) offers the fuller feature set.

## Installation

The package is published to GitHub Packages. Add the repository to your `~/.m2/settings.xml` (adapt as necessary):

```xml
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0
                      http://maven.apache.org/xsd/settings-1.0.0.xsd">

  <activeProfiles>
    <activeProfile>github</activeProfile>
  </activeProfiles>

  <profiles>
    <profile>
      <id>github</id>
      <repositories>
        <repository>
          <id>central</id>
          <url>https://repo1.maven.org/maven2</url>
        </repository>
        <repository>
          <id>github</id>
          <url>https://maven.pkg.github.com/starwit/vision-lib</url>
          <snapshots><enabled>true</enabled></snapshots>
        </repository>
      </repositories>
    </profile>
  </profiles>

  <servers>
    <server>
      <id>github</id>
      <username>YOUR_GITHUB_USER</username>
      <password>GITHUB_TOKEN_WITH_PACKAGE_READ_PERMISSIONS</password>
    </server>
  </servers>
</settings>
```

Then add the dependency to your project:

```xml
<dependency>
  <groupId>de.starwit</groupId>
  <artifactId>vision-lib</artifactId>
  <version>0.3.0</version>
</dependency>
```

## What's available

All classes move `SaeMessage` protobufs and hold resources that must be closed (use try-with-resources).

- **[`de.starwit.pipeline`](src/main/java/de/starwit/pipeline)** – [`SaeReader`](src/main/java/de/starwit/pipeline/SaeReader.java) and [`SaeWriter`](src/main/java/de/starwit/pipeline/SaeWriter.java) read/write messages from/to Valkey streams.
- **[`de.starwit.testing`](src/main/java/de/starwit/testing)** – [`SaeDump`](src/main/java/de/starwit/testing/SaeDump.java) replays a `.saedump` recording as `SaeMessage` objects (see the [format specification](../doc/saedump-format.md)).

## Development

### Building and testing

```bash
mvn verify
```

Tests use [Testcontainers](https://testcontainers.com/) to spin up a Valkey/Redis instance, so a working Docker installation is required.
