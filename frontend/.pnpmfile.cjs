function readPackage(pkg, context) {
  if (pkg.name === 'next') {
    if (pkg.dependencies && pkg.dependencies.sharp) {
      pkg.dependencies.sharp = '^0.35.0';
    }
    if (pkg.optionalDependencies && pkg.optionalDependencies.sharp) {
        pkg.optionalDependencies.sharp = '^0.35.0';
    }
  }
  return pkg;
}

module.exports = {
  hooks: {
    readPackage
  }
};
