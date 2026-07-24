
module.exports = {
  hooks: {
    readPackage(pkg) {
      if (pkg.name === 'next') {
        if (pkg.optionalDependencies && pkg.optionalDependencies.sharp) {
          pkg.optionalDependencies.sharp = '0.35.3';
        }
      }
      return pkg;
    }
  }
};
