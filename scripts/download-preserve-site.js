#!/usr/bin/env node

/**
 * Download and preserve GitHub Pages site content
 *
 * Usage:
 *   node download-preserve-site.js <mode> <site-dir> <pages-url> [options]
 *
 * Modes:
 *   release        - Preserve all content (main, versions, PR previews)
 *
 * Examples:
 *   node download-preserve-site.js release site https://example.github.io/repo
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

function logInfo(message) {
    console.log(`📥 ${message}`);
}

function logSuccess(message) {
    console.log(`✅ ${message}`);
}

function logWarning(message) {
    console.log(`⚠️ ${message}`);
}

function execCommand(command, silent = false) {
    try {
        const result = execSync(command, { encoding: 'utf8', stdio: silent ? 'pipe' : 'inherit' });
        return result.trim();
    } catch (error) {
        if (!silent) {
            logWarning(`Command failed: ${command}`);
        }
        return null;
    }
}

function checkUrlExists(url) {
    try {
        const result = execCommand(`curl -sSL --head "${url}"`, true);
        return result && result.includes('HTTP/2 200');
    } catch (error) {
        return false;
    }
}

function downloadFile(url, outputPath, required = false) {
    try {
        execCommand(`curl -sSL "${url}" -o "${outputPath}"`, true);
        if (fs.existsSync(outputPath)) {
            return true;
        }
    } catch (error) {
        // Download failed
    }

    if (required) {
        logWarning(`Failed to download required file: ${url}`);
    }
    return false;
}

function ensureDirectory(dirPath) {
    if (!fs.existsSync(dirPath)) {
        fs.mkdirSync(dirPath, { recursive: true });
    }
}

function downloadApiFiles(baseUrl, targetDir) {
    ensureDirectory(targetDir);

    const apiFiles = [
        'index.html',
        'experience-api.html',
        'status-api.html',
        'worker-dal-api.html'
    ];

    let downloadedCount = 0;
    for (const file of apiFiles) {
        const url = `${baseUrl}/${file}`;
        const targetPath = path.join(targetDir, file);

        if (downloadFile(url, targetPath)) {
            downloadedCount++;
        }
    }

    return downloadedCount;
}

function preserveMainDocs(pagesUrl, siteDir) {
    logInfo("Checking for main documentation...");

    if (checkUrlExists(`${pagesUrl}/main/`)) {
        logInfo("Main docs exist, preserving them...");
        const mainDir = path.join(siteDir, 'main');
        const downloadedCount = downloadApiFiles(`${pagesUrl}/main`, mainDir);
        logSuccess(`Preserved main documentation (${downloadedCount} files)`);
        return true;
    } else {
        logInfo("No main documentation found");
        return false;
    }
}

function preserveVersionDocs(pagesUrl, siteDir) {
    logInfo("Checking for existing version documentation...");

    if (checkUrlExists(`${pagesUrl}/versions/`)) {
        logInfo("Version directory exists, discovering versions...");
        const versionsDir = path.join(siteDir, 'versions');
        ensureDirectory(versionsDir);

        // Download the versions directory listing to discover versions
        try {
            const versionsHtml = execCommand(`curl -sSL "${pagesUrl}/versions/"`, true);
            if (versionsHtml) {
                // Extract version directory names (looking for href="v*/" patterns)
                const versionMatches = versionsHtml.match(/href="v[^"]*\//g);
                if (versionMatches) {
                    const versions = versionMatches
                        .map(match => match.replace(/href="/g, '').replace(/\/$/g, ''))
                        .filter(version => version.startsWith('v'))
                        .sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));

                    logInfo(`Found ${versions.length} versions: ${versions.join(', ')}`);

                    let preservedCount = 0;
                    for (const version of versions) {
                        if (version) {
                            logInfo(`Preserving version: ${version}`);
                            const versionDir = path.join(versionsDir, version);
                            const downloadedCount = downloadApiFiles(`${pagesUrl}/versions/${version}`, versionDir);
                            if (downloadedCount > 0) {
                                preservedCount++;
                            }
                        }
                    }

                    logSuccess(`Preserved ${preservedCount} version directories`);
                    return preservedCount;
                }
            }
        } catch (error) {
            logWarning("Failed to discover versions from directory listing");
        }
    } else {
        logInfo("No version documentation found");
    }

    return 0;
}

function preservePRPreviews(pagesUrl, siteDir, mode) {
    logInfo("Discovering existing PR preview directories...");

    // First, try to get the main index.html to extract PR directories
    const indexPath = path.join(siteDir, 'index.html');
    let prDirs = [];

    if (fs.existsSync(indexPath)) {
        try {
            const indexContent = fs.readFileSync(indexPath, 'utf8');
            // Extract PR directory names (looking for href="pr-NUMBER/" patterns)
            const prMatches = indexContent.match(/href="pr-[0-9]+\//g);
            if (prMatches) {
                prDirs = prMatches
                    .map(match => match.replace(/href="/g, '').replace(/\/$/g, ''))
                    .filter(dir => dir.startsWith('pr-'))
                    .sort((a, b) => {
                        const numA = parseInt(a.replace('pr-', ''));
                        const numB = parseInt(b.replace('pr-', ''));
                        return numB - numA;
                    });
            }
        } catch (error) {
            logWarning("Failed to parse index.html for PR directories");
        }
    }

    // Also try to discover PR directories from the main site
    try {
        const mainHtml = execCommand(`curl -sSL "${pagesUrl}"`, true);
        if (mainHtml) {
            const prMatches = mainHtml.match(/href="pr-[0-9]+\//g);
            if (prMatches) {
                const discoveredPRs = prMatches
                    .map(match => match.replace(/href="/g, '').replace(/\/$/g, ''))
                    .filter(dir => dir.startsWith('pr-'));

                // Merge with existing PR dirs, remove duplicates
                for (const prDir of discoveredPRs) {
                    if (!prDirs.includes(prDir)) {
                        prDirs.push(prDir);
                    }
                }
            }
        }
    } catch (error) {
        logWarning("Failed to discover PR directories from main site");
    }

    if (prDirs.length > 0) {
        logInfo(`Found ${prDirs.length} PR preview directories: ${prDirs.join(', ')}`);

        let preservedCount = 0;
        for (const prDir of prDirs) {
            const prNumber = prDir.replace('pr-', '');

            logInfo(`Preserving existing PR preview: ${prDir}`);
            if (checkUrlExists(`${pagesUrl}/${prDir}/`)) {
                const prDirPath = path.join(siteDir, prDir);
                const downloadedCount = downloadApiFiles(`${pagesUrl}/${prDir}`, prDirPath);
                if (downloadedCount > 0) {
                    preservedCount++;
                }
            }
        }

        logSuccess(`Preserved ${preservedCount} PR preview directories`);
        return preservedCount;
    } else {
        logInfo("No PR preview directories found");
        return 0;
    }
}

function downloadAndPreserveSite(mode, siteDir, pagesUrl, options = {}) {
    logInfo(`Starting site preservation in ${mode} mode...`);
    logInfo(`Target directory: ${siteDir}`);
    logInfo(`Pages URL: ${pagesUrl}`);

    // Create site directory
    ensureDirectory(siteDir);

    // Check if the site exists
    if (!checkUrlExists(pagesUrl)) {
        logInfo("No existing GitHub Pages site found, creating new one");
        return {
            siteExists: false,
            mainPreserved: false,
            versionsPreserved: 0,
            prPreviewsPreserved: 0
        };
    }

    logInfo("GitHub Pages site exists, downloading...");

    // Download main index.html
    const indexPath = path.join(siteDir, 'index.html');
    const indexDownloaded = downloadFile(`${pagesUrl}/index.html`, indexPath);
    if (!indexDownloaded) {
        logWarning("Failed to download index.html, will create new one");
    }

    // Preserve different types of content
    const mainPreserved = preserveMainDocs(pagesUrl, siteDir);
    const versionsPreserved = preserveVersionDocs(pagesUrl, siteDir);
    const prPreviewsPreserved = preservePRPreviews(pagesUrl, siteDir, mode);

    logSuccess(`Site preservation completed successfully`);

    return {
        siteExists: true,
        mainPreserved,
        versionsPreserved,
        prPreviewsPreserved,
        indexDownloaded
    };
}

function main() {
    const args = process.argv.slice(2);

    if (args.length < 3) {
        console.error('Usage: node download-preserve-site.js <mode> <site-dir> <pages-url> [options]');
        console.error('');
        console.error('Modes:');
        console.error('  release        - Preserve all content (main, versions, PR previews)');
        console.error('');
        process.exit(1);
    }

    const [mode, siteDir, pagesUrl] = args;
    const options = {};

    if (!['release'].includes(mode)) {
        console.error(`Unknown mode: ${mode}`);
        process.exit(1);
    }

    try {
        const result = downloadAndPreserveSite(mode, siteDir, pagesUrl, options);

        // Output summary
        console.log('');
        console.log('📊 Preservation Summary:');
        console.log(`   Site exists: ${result.siteExists ? 'Yes' : 'No'}`);
        if (result.siteExists) {
            console.log(`   Main docs preserved: ${result.mainPreserved ? 'Yes' : 'No'}`);
            console.log(`   Versions preserved: ${result.versionsPreserved}`);
            console.log(`   PR previews preserved: ${result.prPreviewsPreserved}`);
            console.log(`   Index downloaded: ${result.indexDownloaded ? 'Yes' : 'No'}`);
        }

    } catch (error) {
        console.error(`Error: ${error.message}`);
        process.exit(1);
    }
}

if (require.main === module) {
    main();
}
