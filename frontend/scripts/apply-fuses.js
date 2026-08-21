/**
 * electron-builder afterPack hook: flip Electron fuses in the packaged binary.
 *
 * Fuses are bits embedded in the Electron executable that permanently disable
 * runtime capabilities the app never uses. Turning them off removes the
 * ELECTRON_RUN_AS_NODE and NODE_OPTIONS escape hatches, which otherwise let
 * anyone with local file access execute arbitrary code inside our signed binary.
 *
 * Must run before signing, which is why it is an afterPack rather than an
 * afterAllArtifactBuild hook.
 */

const path = require('path');

exports.default = async function applyFuses(context) {
  // @electron/fuses v2 is ESM-only, so it must be imported dynamically from
  // this CommonJS hook. Only a genuinely absent module is tolerated; any other
  // failure must surface, or hardening would be skipped silently.
  let flipFuses;
  let FuseV1Options;
  let FuseVersion;
  try {
    ({ flipFuses, FuseV1Options, FuseVersion } = await import('@electron/fuses'));
  } catch (error) {
    if (error.code === 'ERR_MODULE_NOT_FOUND' || error.code === 'MODULE_NOT_FOUND') {
      console.warn('[fuses] @electron/fuses not installed; skipping fuse hardening.');
      return;
    }
    throw error;
  }

  const { appOutDir, packager, electronPlatformName } = context;
  const appName = packager.appInfo.productFilename;

  let executable;
  if (electronPlatformName === 'darwin') {
    executable = path.join(appOutDir, `${appName}.app`, 'Contents', 'MacOS', appName);
  } else if (electronPlatformName === 'win32') {
    executable = path.join(appOutDir, `${appName}.exe`);
  } else if (electronPlatformName === 'linux') {
    executable = path.join(appOutDir, packager.executableName || appName);
  } else {
    console.warn(`[fuses] Unsupported platform ${electronPlatformName}; skipping.`);
    return;
  }

  await flipFuses(executable, {
    version: FuseVersion.V1,
    resetAdHocDarwinSignature: electronPlatformName === 'darwin',

    // Deny running the binary as a plain Node process.
    [FuseV1Options.RunAsNode]: false,
    // Deny --inspect and friends attaching a debugger to production builds.
    [FuseV1Options.EnableNodeCliInspectArguments]: false,
    // Deny NODE_OPTIONS injecting flags or preload scripts.
    [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
    // Detect tampering with the packaged asar archive.
    [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
    // Refuse to load application code from outside the asar.
    [FuseV1Options.OnlyLoadAppFromAsar]: true,
    // The UI is served over app://, so file:// needs no extra privileges.
    [FuseV1Options.GrantFileProtocolExtraPrivileges]: false,
  });

  console.log(`[fuses] Hardened ${path.basename(executable)} (${electronPlatformName}).`);
};
