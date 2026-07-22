function readPackage(pkg) {
  for (const dependencyGroup of ['dependencies', 'peerDependencies', 'devDependencies']) {
    if (pkg[dependencyGroup] && pkg[dependencyGroup].postcss) {
      pkg[dependencyGroup].postcss = '^8.5.16';
    }
  }
  for (const dependencyGroup of ['dependencies', 'peerDependencies', 'devDependencies', 'optionalDependencies']) {
    if (pkg[dependencyGroup] && pkg[dependencyGroup].sharp) {
      pkg[dependencyGroup].sharp = '0.35.3';
    }
  }
  return pkg;
}

module.exports = {
  hooks: {
    readPackage
  }
};
