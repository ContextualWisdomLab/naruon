function readPackage(pkg, context) {
  if (pkg.dependencies && pkg.dependencies.sharp) {
    pkg.dependencies.sharp = '0.35.3';
  }
  return pkg;
}

module.exports = {
  hooks: {
    readPackage
  }
}
