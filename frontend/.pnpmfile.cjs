module.exports = {
  hooks: {
    readPackage(pkg) {
      if (pkg.dependencies && pkg.dependencies.postcss) {
        pkg.dependencies.postcss = '^8.5.15';
      }
      if (pkg.peerDependencies && pkg.peerDependencies.postcss) {
        pkg.peerDependencies.postcss = '^8.5.15';
      }
      if (pkg.devDependencies && pkg.devDependencies.postcss) {
        pkg.devDependencies.postcss = '^8.5.15';
      }
      if (pkg.dependencies && pkg.dependencies.sharp) {
        pkg.dependencies.sharp = ">=0.35.3";
      }
      if (pkg.devDependencies && pkg.devDependencies.sharp) {
        pkg.devDependencies.sharp = ">=0.35.3";
      }
      if (pkg.optionalDependencies && pkg.optionalDependencies.sharp) {
        pkg.optionalDependencies.sharp = ">=0.35.3";
      }
      return pkg;
    }
  }
};
