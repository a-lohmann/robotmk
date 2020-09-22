# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## Unreleased

### Added

- Plugin: Optional execution of robot with the currently logged in user (#44); makes
  it possible to use libraries like SikuliX, ImageHorizon etc.

### Changed

- The default path of `outputdir` has changed on Windows and is now fixed to c:/windows/temp.
  Debugging is alot more easier when we know where to search for the XML.


## [v0.1.3] - 2020-0-16
### Added 

- Check: Introduce CRITICAL state for thresholds (#22)
- Check: Add WATO option: include execution timestamp into first line (#41)

### Fixed

- Check: Solved check crash when only perfdata rule active, not threshold (#40)

## [v0.1.2] - 2020-07-10

### Fixed

- Bakery: Wrong formatting of variable argument (#38)
- Plugin: Backslash escaping of CheckMK programdata path (#37)

## [v0.1.1] - 2020-07-01

- First Release; Bakery, Plugin and Check are working together


## [vx.x.x] - yyyy-mm-dd
### Added

### Changed

### Fixed

### Removed

### Deprecated
