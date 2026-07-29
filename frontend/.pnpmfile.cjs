function readPackage(pkg, context) {
  if (pkg.name === 'next') {
    pkg.dependencies.sharp = '0.35.0';
    context.log('Fixed next sharp dependency');
  }
  return pkg;
}

module.exports = {
  hooks: {
    readPackage
  }
};
