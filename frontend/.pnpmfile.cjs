function readPackage(pkg, context) {
  if (pkg.dependencies && pkg.dependencies.sharp) {
    pkg.dependencies.sharp = '0.35.5'
  }
  if (pkg.name === 'next' && pkg.dependencies && pkg.dependencies.sharp) {
    pkg.dependencies.sharp = '0.35.5'
  }
  if (pkg.name === 'next' && pkg.peerDependencies && pkg.peerDependencies.sharp) {
    pkg.peerDependencies.sharp = '0.35.5'
  }
  if (pkg.devDependencies && pkg.devDependencies.sharp) {
    pkg.devDependencies.sharp = '0.35.5'
  }
  if (pkg.optionalDependencies && pkg.optionalDependencies.sharp) {
    pkg.optionalDependencies.sharp = '0.35.5'
  }
  return pkg
}
module.exports = {
  hooks: {
    readPackage
  }
}
