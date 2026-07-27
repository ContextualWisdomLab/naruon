module.exports = {
  hooks: {
    readPackage(pkg) {
      if (pkg.dependencies && pkg.dependencies.postcss) {
        pkg.dependencies.postcss = '^8.5.23';
      }
      if (pkg.peerDependencies && pkg.peerDependencies.postcss) {
        pkg.peerDependencies.postcss = '^8.5.23';
      }
      if (pkg.devDependencies && pkg.devDependencies.postcss) {
        pkg.devDependencies.postcss = '^8.5.23';
      }
      return pkg;
    }
  }
};
