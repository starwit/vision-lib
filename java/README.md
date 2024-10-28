# vision-lib Java edition
## How-To Use
### Java / Maven
- Add maven repository to your `~/.m2/settings.xml` (adapt example / your config as necessary):
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
            <snapshots>
                <enabled>true</enabled>
            </snapshots>
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

- Add dependency to your project:
    ```xml
    <dependency>
      <groupId>de.starwit</groupId>
      <artifactId>vision-lib</artifactId>
      <version>0.2.0</version>
    </dependency>
    ```
