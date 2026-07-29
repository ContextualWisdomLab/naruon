function readPackage(pkg, context) {
  if (pkg.name === 'next') {
    pkg.dependencies.sharp = '0.35.0';
    pkg.dependencies['brace-expansion'] = '^5.0.8';
    context.log('Fixed next sharp dependency');
  }
  return pkg;
}

module.exports = {
  hooks: {
    readPackage
  }
};
