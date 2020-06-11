import json
import zipfile
import io
import tarfile
import platform
import stat
import os
import pathlib
import sys
import subprocess
import shutil
import urllib.request

# Global Variables
home = os.path.expanduser("~")

root = os.path.join(home, ".neopo")
DEPS = os.path.join(home, ".particle", "toolchains")

raspberry_pi_gcc_arm = "https://github.com/nrobinson2000/neopo/releases/download/0.0.1/gcc-arm-v5.3.1-raspberry-pi.tar.gz"
running_on_windows = platform.system() == "Windows"

particle_cli = os.path.join(DEPS, "particle")
if running_on_windows:
    particle_cli = os.path.join(DEPS, "particle.exe")

jsonFiles = {
    "firmware": os.path.join(root, "cache", "firmware.json"),
    "toolchains": os.path.join(root, "cache", "toolchains.json"),
    "platforms": os.path.join(root, "cache", "platforms.json"),
    "manifest": os.path.join(root, "cache", "manifest.json")
}

vscodeFiles = {
    "dir": os.path.join(DEPS, "vscode"),
    "launch": os.path.join(DEPS, "vscode", "launch.json"),
    "settings": os.path.join(DEPS, "vscode", "settings.json")
}

extensionFiles = {
    "bin": "extension/src/cli/bin",
    "manifest": "extension/src/compiler/manifest.json",
    "launch": "extension/src/cli/vscode/launch.json",
    "settings": "extension/src/cli/vscode/settings.json"
}

projectFiles = {
    "launch": os.path.join(".vscode", "launch.json"),
    "settings": os.path.join(".vscode", "settings.json"),
    "properties": "project.properties"
}

# Find the Workbench extension URL from the Visual Studio Marketplace
def getExtensionURL():
    print("Finding Workbench extension URL...")
    payload = '{"assetTypes":null,"filters":[{"criteria":[{"filterType":7,"value":"particle.particle-vscode-core"}],"direction":2,"pageSize":100,"pageNumber":1,"sortBy":0,"sortOrder":0,"pagingToken":null}],"flags":103}'

    request = urllib.request.Request(
        "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery",
        method="POST",
        headers={
            "content-type":
            "application/json",
            "accept":
            "application/json;api-version=6.0-preview.1;excludeUrls=true",
        },
        data=payload.encode("utf-8"),
    )

    with urllib.request.urlopen(request) as response:
        content = response.read()

    data = json.loads(content.decode("utf-8"))
    return data["results"][0]["extensions"][0]["versions"][0]["files"][-1]["source"]

# Download the the Workbench extension from the URL
def getExtension(url):
    print("Downloading Workbench extension...")
    with urllib.request.urlopen(url) as response:
        content = response.read()
    return zipfile.ZipFile(io.BytesIO(content), "r")

# Load a file from a ZIP
def getFile(file, path):
    content = file.read(path)
    return content

# Download the specified dependency
def downloadDep(dep, updateManifest):
    if updateManifest:
        writeManifest(dep)

    name, version, url = dep["name"], dep["version"], dep["url"]
    print("Downloading dependency", name, "version", version + "...")

    with urllib.request.urlopen(url) as response:
        content = response.read()

    path = os.path.join(DEPS, name, version)
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)

    fileName = os.path.join(path, name + "-v" + version + ".tar.gz")
    with open(fileName, "wb") as gzFile:
        gzFile.write(content)

    with tarfile.open(fileName, "r:gz") as file:
        file.extractall(path)

    os.remove(fileName)

# Write JSON data to a file
def writeFile(content, path):
    with open(path, "wb") as file:
        file.write(content)

# Write an executable dependency to a file
def writeExecutable(content, path):
    with open(path, "wb") as file:
        file.write(content)
        st = os.stat(file.name)
        os.chmod(file.name, st.st_mode | stat.S_IEXEC)

# Download extension manifest and simple dependencies
def getDeps():
    osPlatform = platform.system().lower()    
    osArch = platform.machine().lower() if running_on_windows else "amd64" if platform.machine() == "x86_64" else "arm"

    extension = getExtension(getExtensionURL())
    pathlib.Path(vscodeFiles["dir"]).mkdir(parents=True, exist_ok=True)
    manifest = getFile(extension, extensionFiles["manifest"])

    particle_bin = "particle.exe" if running_on_windows else "particle"

    particle = getFile(
        extension, extensionFiles["bin"] + "/" + osPlatform + "/" + osArch +
        "/" + particle_bin)
    launch = getFile(extension, extensionFiles["launch"])
    settings = getFile(extension, extensionFiles["settings"])

    writeFile(launch, vscodeFiles["launch"])
    writeFile(settings, vscodeFiles["settings"])
    writeExecutable(particle, particle_cli)
    createManifest()

    data = json.loads(manifest.decode("utf-8"))
    return data

# Update the manifest JSON file
def writeManifest(dep):
    with open(jsonFiles["manifest"], "r+") as file:
        try:
            manifest = json.load(file)
        except json.decoder.JSONDecodeError:
            manifest = {}

        manifest[dep["name"]] = dep["version"]
        file.seek(0)
        json.dump(manifest, file, indent=4)
        file.truncate()

# Create the manifest file
def createManifest():
    if not os.path.isfile(jsonFiles["manifest"]):
        with open(jsonFiles["manifest"], "w") as file:
            pass

# Load settings from the JSON file
def loadManifest(tupleOrDict):
    with open(jsonFiles["manifest"], "r") as file:
        data = json.load(file)
        if tupleOrDict:
            return (
                data["gcc-arm"],
                data["buildscripts"],
                data["buildtools"],
                data["deviceOS"],
            )
        else:
            return {
                "gcc-arm": data["gcc-arm"],
                "buildscripts": data["buildscripts"],
                "buildtools": data["buildtools"],
                "deviceOS": data["deviceOS"],
                "openocd": data["openocd"],
            }

# Write an object to JSON file
def writeJSONcache(data, key):
    with open(os.path.join(DEPS, key + ".json"), "w") as file:
        keyData = data[key]
        json.dump(keyData, file, indent=4)

# Attempt to download deviceOS version not specified in manifest (experimental)
def downloadUnlisted(version):
    firmware = {
        "name": "deviceOS",
        "version": version,
        "url": "https://binaries.particle.io/device-os/v" + version + ".tar.gz"
    }

    print("Trying binaries.particle.io/device-os...")

    try:
        downloadDep(firmware, False)
        return
    except urllib.error.HTTPError:
        print("DeviceOS version", version, "not found!")
        print()

    # Try to download from github
    firmware = {
        "name": "deviceOS",
        "version": version,
        "url": "https://github.com/particle-iot/device-os/archive/v" + version + ".tar.gz"
    }

    print("Trying github.com/particle-iot/device-os...")

    try:
        downloadDep(firmware, False)
        return
    except urllib.error.HTTPError:
        print("DeviceOS version", version, "not found!")

# Wrapper for [download-unlisted]
def downloadUnlisted_command():
    try:
        downloadUnlisted(sys.argv[2])
    except IndexError:
        print("You must specify a deviceOS version!")

# Download a specific deviceOS version
def downloadFirmware(version):
    firmware = getFirmwareData(version)
    if firmware:
        downloadDep(firmware, False)
    else:
        print("Could not download deviceOS version", version + "!")

# Install or update neopo dependencies (not the neopo script)
def installOrUpdate(install):
    if install:
        print("Installing neopo...")
    else:
        print("Updating dependencies...")

    dependencies = ["compilers", "tools", "scripts", "debuggers"]
    caches = ["firmware", "platforms", "toolchains"]

    data = getDeps()
    depJSON = []
    depJSON.append(data["firmware"][0])

    for dep in dependencies:
        depJSON.append(data[dep][platform.system().lower()]["x64"][0])

    # Support for Raspberry Pi
    if platform.machine() == "armv7l":
        for dep in depJSON:
            if dep["name"] == "gcc-arm":
                dep["url"] = raspberry_pi_gcc_arm
                break

    for key in caches:
        writeJSONcache(data, key)

    if install:
        for dep in depJSON:
            downloadDep(dep, True)
        print("Finished installation. To create a project use:")
        print("\tneopo create <project>")
    else:
        for dep in depJSON:
            manifest = loadManifest(False)
            new = int(dep["version"].split("-")[0].replace(".", ""))
            old = int(manifest[dep["name"]].split("-")[0].replace(".", ""))
            if new > old:
                downloadDep(dep, True)
        print("Dependencies are up to date!")

# Delete the neopo script from the system
def uninstall():
    execpath = sys.argv[0]
    print("Are you sure you want to uninstall neopo at", execpath + "?")

    answer = input("(Y/N): ")
    if answer.lower() != "y":
        print("Aborted.")
        return

    try:
        os.remove(execpath)
    except PermissionError:
        print("Could not delete", execpath)
        print("Try running with sudo.")
        exit(1)

    print("Uninstalled neopo.")
    print(
        "Note: The .particle directory may still exist (remove it with `rm -rf ~/.particle`)"
    )

# Create a Particle project and copy in Workbench settings
def create(path, name):
    tempEnv = os.environ.copy()
    addToPath(tempEnv, DEPS)

    returncode = subprocess.run(
        ["particle", "project", "create", path, "--name", name],
        env=tempEnv,
        shell=running_on_windows).returncode
    if returncode:
        exit(returncode)

    #TODO: Default device in manifest.json
    device = "argon"
    version = loadManifest(True)[-1]
    configure(os.path.join(path, name), device, version)

# Get a deviceOS dependency from a version
def getFirmwareData(version):
    with open(jsonFiles["firmware"], "r") as firmwareFile:
        data = json.load(firmwareFile)
        for entry in data:
            if entry["version"] == version:
                return entry
        return False

# Convert between platform IDs and device names
def platformConvert(data, key1, key2):
    with open(jsonFiles["platforms"], "r") as platformFile:
        platforms = json.load(platformFile)
        for platform in platforms:
            if platform[key1] == data:
                return platform[key2]
        return False

# List the supported platform IDs for a given version
def getSupportedPlatforms(version):
    with open(jsonFiles["toolchains"], "r") as toolchainsFile:
        toolchains = json.load(toolchainsFile)
        for toolchain in toolchains:
            if toolchain["firmware"] == "deviceOS@" + version:
                return toolchain["platforms"]
        return False

# Verify platform and deviceOS version and download deviceOS dependency if required
def checkFirmwareVersion(platform, version):
    firmware = getFirmwareData(version)
    platformID = platformConvert(platform, "name", "id")

    if not platformID:
        print("Invalid platform", platform + "!")
        return False

    if not firmware:
        print("Invalid deviceOS version", version + "!")
        return False

    if not platformID in getSupportedPlatforms(version):
        print("Platform", platform, " is not supported in deviceOS version",
              version + "!")
        return False

    path = os.path.join(DEPS, "deviceOS", version)
    if os.path.isdir(path):
        return True

    downloadDep(firmware, False)
    return True

# Modify Workbench settings in a project (platform, firmwareVersion)
def configure(projectPath, platform, firmwareVersion):
    if not checkFirmwareVersion(platform, firmwareVersion):
        exit(1)

    if not os.path.isfile(os.path.join(projectPath, projectFiles["settings"])):
        pathlib.Path(os.path.join(projectPath, ".vscode")).mkdir(parents=True,
                                                                 exist_ok=True)
        shutil.copyfile(vscodeFiles["launch"],
                        os.path.join(projectPath, projectFiles["launch"]))
        shutil.copyfile(vscodeFiles["settings"],
                        os.path.join(projectPath, projectFiles["settings"]))

    writeSettings(projectPath, platform, firmwareVersion)
    print("Configured project", projectPath + ":")
    print("\tparticle.targetPlatform:", platform)
    print("\tparticle.firmwareVersion:", firmwareVersion)

# Load Workbench settings from a project
def getSettings(projectPath):
    with open(os.path.join(projectPath, projectFiles["settings"]),
              "r+") as settings:
        data = json.loads(settings.read())
        return (data["particle.targetPlatform"],
                data["particle.firmwareVersion"])

# Update Workbench settings in a project
def writeSettings(projectPath, platform, version):
    with open(os.path.join(projectPath, projectFiles["settings"]),
              "r+") as settings:
        data = json.loads(settings.read())
        data["particle.targetPlatform"] = platform
        data["particle.firmwareVersion"] = version
        settings.seek(0)
        json.dump(data, settings, indent=4)
        settings.truncate()

# Print help information directly from Makefile
def build_help():
    build(None, None, True, False)

# Create the path string for a given deviceOS version
def getFirmwarePath(version):
    deviceOSPath = os.path.join(DEPS, "deviceOS", version)
    legacy = "firmware-" + version
    github = "device-os-" + version

    if os.path.isdir(os.path.join(deviceOSPath, legacy)):
        deviceOSPath = os.path.join(deviceOSPath, legacy)

    if os.path.isdir(os.path.join(deviceOSPath, github)):
        deviceOSPath = os.path.join(deviceOSPath, github)

    return deviceOSPath

# Add a path to an environment
def addToPath(environment, path):
    if running_on_windows:
        environment["PATH"] = path + ";" + environment["PATH"]
    else:
        environment["PATH"] += ":" + path

# Use the Makefile to build the specified target
def build(projectPath, command, helpOnly, doVerbose):
    compilerVersion, scriptVersion, toolsVersion, firmwareVersion = loadManifest(
        True)
    tempEnv = os.environ.copy()
    addToPath(tempEnv, os.path.join(DEPS, "gcc-arm", compilerVersion, "bin"))

    particle = particle_cli

    if running_on_windows:
        addToPath(tempEnv, os.path.join(DEPS, "buildtools", toolsVersion,
                                        "bin"))
        particle = particle.replace("C:\\", "/cygdrive/c/")
        particle = particle.replace("\\", "/")
    else:
        addToPath(tempEnv, os.path.join(DEPS, "buildtools", toolsVersion))

    process = [
        "make", "-sf",
        os.path.join(DEPS, "buildscripts", scriptVersion, "Makefile"),
        "PARTICLE_CLI_PATH=" + particle
    ]

    # Remove [s] flag from make to get verbose output
    if doVerbose:
        process[1] = "-f"

    if helpOnly:
        process.append("help")
    else:
        try:
            devicePlatform, firmwareVersion = getSettings(projectPath)
        except FileNotFoundError:
            if os.path.isfile(
                    os.path.join(projectPath, projectFiles['properties'])):
                print("Project not configured!")
                print("Use: neopo configure <platform> <version> <project>")
                return
            else:
                raise

        if running_on_windows:
            projectPath = projectPath.replace("\\", "\\\\")

        deviceOSPath = getFirmwarePath(firmwareVersion)
        process.append("APPDIR=" + projectPath)
        process.append("DEVICE_OS_PATH=" + deviceOSPath)
        process.append("PLATFORM=" + devicePlatform)
        process.append(command)

    returncode = subprocess.run(process, env=tempEnv,
                                shell=running_on_windows).returncode
    if returncode:
        exit(returncode)

# Parse the project path from the specified index and run a Makefile target
def buildCommand(command, index):
    verboseIndex = index
    doVerbose = False
    project = None

    try:
        if not sys.argv[index].startswith("-"):
            project = os.path.abspath(sys.argv[index])
            verboseIndex += 1
        else:
            project = os.getcwd()
    except IndexError:
        project = os.getcwd()
        verboseIndex = index

    try:
        doVerbose = sys.argv[verboseIndex] == "-v"
    except IndexError:
        pass

    try:
        build(project, command, False, doVerbose)
    except FileNotFoundError:
        print("Invalid project!")

# Print available versions compressed (for completion)
def versions_compressed():
    with open(jsonFiles["firmware"], "r") as firmwareFile:
        data = json.load(firmwareFile)
        output = ""
        for entry in data:
            output += entry["version"] + " "
        print(output)

# Print available platforms (for completion)
def platforms_command():
    with open(jsonFiles["platforms"], "r") as platformFile:
        data = json.load(platformFile)
        output = ""
        for entry in data:
            output += entry["name"] + " "
        print(output)

# Find all valid projects in PWD (for completion)
def findValidProjects():
    (_, dirs, _) = next(os.walk(os.getcwd()))
    output = ""
    for dir in dirs:
        if os.access(os.path.join(dir, "project.properties"), os.R_OK):
            output += dir + " "
    print(output)

# Find all makefile targets (for completion)
def getMakefileTargets():
    with open(jsonFiles["manifest"], "r") as manifest:
        data = json.load(manifest)
        with open(
                os.path.join(DEPS, "buildscripts", data["buildscripts"],
                             "Makefile")) as makefile:
            contents = makefile.readlines()
            sep = ".PHONY: "
            for line in contents:
                if line.startswith(sep):
                    print(line.partition(sep)[2].strip("\n"))
                    return

# Print available versions and platforms
def versions():
    with open(jsonFiles["firmware"], "r") as firmwareFile:
        data = json.load(firmwareFile)
        print("Available deviceOS versions:")
        print()
        data.reverse()
        for entry in data:
            version = entry["version"]
            platforms = getSupportedPlatforms(version)
            devices = []
            for platform in platforms:
                devices.append(platformConvert(platform, "id", "name"))

            devicesStr = devices[0]
            for device in devices[1:]:
                devicesStr += ", " + device

            print("  ", version + "\t", "[", devicesStr, "]")

        print()
        print("To configure a project use:")
        print("\tneopo configure <platform> <version> <project>")

# Wrapper for [config/configure]
def configure_command():
    try:
        platform = sys.argv[2]
        version = sys.argv[3]
    except IndexError:
        print("You must supply platform and deviceOS version!")
        return
    try:
        projectPath = sys.argv[4]
    except IndexError:
        projectPath = os.getcwd()

    configure(projectPath, platform, version)

# Wrapper for [run]
def run_command():
    try:
        command = sys.argv[2]
    except IndexError:
        build_help()
        print("You must supply a Makefile target!")
        return

    buildCommand(command, 3)

# Wrapper for [create]
def create_command():
    try:
        projectPath = sys.argv[2]
    except IndexError:
        print("You must supply a path for the project!")
        return

    projectPath = os.path.abspath(projectPath)
    create(os.path.dirname(projectPath), os.path.basename(projectPath))

# Wrapper for [get]
def get_command():
    try:
        version = sys.argv[2]
        downloadFirmware(version)
    except IndexError:
        print("You must specify a deviceOS version!")

# More wrappers
def flash_command():
    buildCommand("flash-user", 2)
def compile_command():
    buildCommand("compile-user", 2)
def flash_all_command():
    buildCommand("flash-all", 2)
def clean_command():
    buildCommand("clean-user", 2)
def install_command():
    installOrUpdate(True)
def update_command():
    installOrUpdate(False)

# Print help information about the program
def print_help():
    print("""Usage: neopo [OPTIONS] [PROJECT] [-v]

Options:
    General Options:
        help
        install
        uninstall
        versions
        create <project>

    Build Options:
        compile|build [project] [-v]
        flash [project] [-v]
        flash-all [project] [-v]
        clean [project] [-v]

    Special Options:
        run <target> [project] [-v]
        configure <platform> <version> [project]

    Dependency Options:
        update
        get <version>
        """)

# Print all commands (for completion)
def options():
    print(*commands.keys(), sep=" ")

# Available options
commands = {
    "help": print_help,
    "install": install_command,
    "uninstall": uninstall,
    "versions": versions,
    "create": create_command,
    "compile": compile_command,
    "build": compile_command,
    "flash": flash_command,
    "flash-all": flash_all_command,
    "clean": clean_command,
    "run": run_command,
    "configure": configure_command,
    "update": update_command,
    "get": get_command,
    "list-versions": versions_compressed,
    "platforms": platforms_command,
    "projects": findValidProjects,
    "targets": getMakefileTargets,
    "options": options,
    "download-unlisted": downloadUnlisted_command
}

# Evaluate command-line arguments and call necessary functions
def main():
    if len(sys.argv) == 1:
        print_help()
    elif sys.argv[1] in commands:
        commands[sys.argv[1]]()
    else:
        print("Invalid command!")
        print_help()

if __name__ == "__main__":
    main()