function readPackage(pkg) {
  if (pkg.dependencies && pkg.dependencies.sharp) {
    pkg.dependencies.sharp = '^0.35.3';
  }
  if (pkg.optionalDependencies && pkg.optionalDependencies.sharp) {
    pkg.optionalDependencies.sharp = '^0.35.3';
  }
  if (pkg.dependencies && pkg.dependencies['minimatch']) {
    if (pkg.dependencies['minimatch'].startsWith('^3') || pkg.dependencies['minimatch'].startsWith('3')) {
      pkg.dependencies['minimatch'] = '^3.1.2';
    }
  }
  return pkg;
}
module.exports = {
  hooks: {
    readPackage
  }
}
