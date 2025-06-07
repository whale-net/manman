#!/usr/bin/env node

/**
 * Generate HTML documentation pages for ManMan API docs
 * 
 * Usage:
 *   node generate-docs-html.js <type> <output-file> [options]
 * 
 * Types:
 *   pr-index <pr-number> <pr-title> <branch> <sha>
 *   release-index <version> <sha>
 *   main-index
 *   hub-index [pr-dirs...] [version-dirs...]
 *   dynamic-pr-hub <site-dir> <current-pr> <current-pr-title>
 *   dynamic-release-hub <site-dir>
 *   dynamic-cleanup-hub <site-dir>
 *   static-main-hub
 */

const fs = require('fs');
const path = require('path');

const SHARED_CSS = `
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem;
    background: #f8fafc;
}
.header {
    text-align: center;
    margin-bottom: 3rem;
    padding-bottom: 2rem;
    border-bottom: 2px solid #e2e8f0;
}
.banner {
    padding: 1rem;
    border-radius: 8px;
    margin-bottom: 2rem;
    text-align: center;
    color: white;
}
.pr-banner {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.version-banner {
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
}
.main-banner {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}
.api-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 2rem;
    margin-top: 2rem;
}
.api-card {
    background: white;
    border-radius: 12px;
    padding: 2rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    border: 1px solid #e2e8f0;
    transition: transform 0.2s, box-shadow 0.2s;
}
.api-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 25px -3px rgba(0, 0, 0, 0.1);
}
.api-title {
    font-size: 1.5rem;
    font-weight: 600;
    margin-bottom: 1rem;
    color: #1e293b;
}
.api-description {
    color: #64748b;
    margin-bottom: 1.5rem;
    line-height: 1.6;
}
.api-link {
    display: inline-block;
    background: #3b82f6;
    color: white;
    padding: 0.75rem 1.5rem;
    border-radius: 8px;
    text-decoration: none;
    font-weight: 500;
    transition: background 0.2s;
}
.api-link:hover {
    background: #2563eb;
}
.build-info {
    background: #f1f5f9;
    border-radius: 8px;
    padding: 1rem;
    margin-top: 2rem;
    font-size: 0.875rem;
    color: #475569;
}
.back-link {
    display: inline-block;
    margin-bottom: 1rem;
    color: #6b7280;
    text-decoration: none;
}
.back-link:hover {
    color: #374151;
}`;

const HUB_CSS = `
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 1000px;
    margin: 0 auto;
    padding: 2rem;
    background: #f8fafc;
}
.header {
    text-align: center;
    margin-bottom: 3rem;
    padding-bottom: 2rem;
    border-bottom: 2px solid #e2e8f0;
}
.section {
    margin-bottom: 3rem;
}
.section-title {
    font-size: 1.5rem;
    font-weight: 600;
    margin-bottom: 1rem;
    color: #1e293b;
}
.card-grid, .preview-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
    gap: 1.5rem;
}
.card, .preview-card {
    background: white;
    border-radius: 12px;
    padding: 2rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    border: 1px solid #e2e8f0;
}
.main-docs {
    border-left: 4px solid #10b981;
}
.pr-preview {
    border-left: 4px solid #f59e0b;
}
.version-docs {
    border-left: 4px solid #6366f1;
}
.card-title, .preview-title {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 1rem;
    color: #1e293b;
}
.card-description {
    color: #64748b;
    margin-bottom: 1.5rem;
    line-height: 1.6;
}
.card-link, .preview-link {
    display: inline-block;
    background: #3b82f6;
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    text-decoration: none;
    font-weight: 500;
    margin-top: 1rem;
}
.main-docs .card-link, .main-docs .preview-link {
    background: #10b981;
}
.pr-preview .card-link, .pr-preview .preview-link {
    background: #f59e0b;
}
.version-docs .card-link {
    background: #6366f1;
}
.info-section {
    background: #f8fafc;
    border-radius: 8px;
    padding: 1.5rem;
    margin-top: 2rem;
    border: 1px solid #e2e8f0;
}
.empty-state {
    text-align: center;
    color: #64748b;
    font-style: italic;
}`;

const API_CARDS = `
<div class="api-card">
    <h2 class="api-title">Experience API</h2>
    <p class="api-description">Game server management and user-facing functionality. This is the primary API for hosting game servers and managing user experiences.</p>
    <a href="experience-api.html" class="api-link">View Documentation</a>
</div>

<div class="api-card">
    <h2 class="api-title">Status API</h2>
    <p class="api-description">Status and monitoring functionality. Provides health checks, metrics, and monitoring endpoints for all ManMan services.</p>
    <a href="status-api.html" class="api-link">View Documentation</a>
</div>

<div class="api-card">
    <h2 class="api-title">Worker DAL API</h2>
    <p class="api-description">Data access endpoints for worker services. Internal API used by worker processes for database operations.</p>
    <a href="worker-dal-api.html" class="api-link">View Documentation</a>
</div>`;

function generatePRIndex(prNumber, prTitle, branch, sha, outputFile) {
    const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ManMan API Documentation - PR #${prNumber}</title>
    <style>${SHARED_CSS}</style>
</head>
<body>
    <a href="../" class="back-link">← Back to Documentation Hub</a>

    <div class="banner pr-banner">
        <h2>🔍 Pull Request Preview</h2>
        <p>This is a preview of the API documentation for PR #${prNumber}</p>
        <p><strong>${prTitle}</strong></p>
    </div>

    <div class="header">
        <h1>ManMan API Documentation</h1>
        <p>Interactive API documentation for all ManMan services</p>
    </div>

    <div class="api-grid">
        ${API_CARDS}
    </div>

    <div class="build-info">
        <strong>PR Information:</strong><br>
        PR: <code>#${prNumber}</code><br>
        Title: <code>${prTitle}</code><br>
        Branch: <code>${branch}</code><br>
        Commit: <code>${sha}</code><br>
        Generated at: <code>${new Date().toISOString()}</code>
    </div>
</body>
</html>`;

    fs.writeFileSync(outputFile, html);
    console.log(`✅ Generated PR index page: ${outputFile}`);
}

function generateReleaseIndex(version, sha, outputFile) {
    const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ManMan API Documentation - ${version}</title>
    <style>${SHARED_CSS}</style>
</head>
<body>
    <a href="../../" class="back-link">← Back to Documentation Hub</a>

    <div class="banner version-banner">
        <h2>📦 Release Documentation</h2>
        <p><strong>Version: ${version}</strong></p>
        <p>Official API documentation for this release</p>
    </div>

    <div class="header">
        <h1>ManMan API Documentation</h1>
        <p>Interactive API documentation for all ManMan services</p>
    </div>

    <div class="api-grid">
        ${API_CARDS}
    </div>

    <div class="build-info">
        <strong>Release Information:</strong><br>
        Version: <code>${version}</code><br>
        Generated from commit: <code>${sha}</code><br>
        Generated at: <code>${new Date().toISOString()}</code>
    </div>
</body>
</html>`;

    fs.writeFileSync(outputFile, html);
    console.log(`✅ Generated release index page: ${outputFile}`);
}

function generateMainIndex(outputFile) {
    const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ManMan API Documentation</title>
    <style>${SHARED_CSS}</style>
</head>
<body>
    <a href="../" class="back-link">← Back to Documentation Hub</a>

    <div class="banner main-banner">
        <h2>🚀 Latest Release</h2>
        <p>This is the latest stable API documentation</p>
    </div>

    <div class="header">
        <h1>ManMan API Documentation</h1>
        <p>Interactive API documentation for all ManMan services</p>
    </div>

    <div class="api-grid">
        ${API_CARDS}
    </div>

    <div class="build-info">
        <strong>Documentation Type:</strong> Latest Release<br>
        <strong>Generated at:</strong> <code>${new Date().toISOString()}</code>
    </div>
</body>
</html>`;

    fs.writeFileSync(outputFile, html);
    console.log(`✅ Generated main index page: ${outputFile}`);
}

function generateHubIndex(prDirs = [], versionDirs = [], outputFile) {
    // Generate PR preview cards
    let prCardsHtml = '';
    if (prDirs.length > 0) {
        for (const prDir of prDirs) {
            const prNumber = prDir.replace('pr-', '');
            prCardsHtml += `
                <div class="card pr-preview">
                    <h3 class="card-title">🔍 PR #${prNumber} Preview</h3>
                    <p class="card-description">Preview of API changes in pull request #${prNumber}</p>
                    <a href="${prDir}/" class="card-link">View PR Preview</a>
                </div>`;
        }
    } else {
        prCardsHtml = '<div class="card"><p class="card-description">No active PR previews</p></div>';
    }

    // Generate version cards
    let versionCardsHtml = '';
    if (versionDirs.length > 0) {
        for (const versionDir of versionDirs) {
            versionCardsHtml += `
                <div class="card version-docs">
                    <h3 class="card-title">📦 ${versionDir}</h3>
                    <p class="card-description">API documentation for release ${versionDir}</p>
                    <a href="versions/${versionDir}/" class="card-link">View Documentation</a>
                </div>`;
        }
    } else {
        versionCardsHtml = '<div class="card"><p class="card-description">No release versions available yet</p></div>';
    }

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ManMan API Documentation Hub</title>
    <style>${HUB_CSS}</style>
</head>
<body>
    <div class="header">
        <h1>ManMan API Documentation Hub</h1>
        <p>Access API documentation for all versions and PR previews</p>
    </div>

    <div class="section">
        <h2 class="section-title">🚀 Current Documentation</h2>
        <div class="card-grid">
            <div class="card main-docs">
                <h3 class="card-title">Latest Release Documentation</h3>
                <p class="card-description">Official API documentation from the latest stable release</p>
                <a href="main/" class="card-link">View Documentation</a>
            </div>
        </div>
    </div>

    <div class="section">
        <h2 class="section-title">📚 Release Versions (${versionDirs.length})</h2>
        <div class="card-grid">
            ${versionCardsHtml}
        </div>
    </div>

    <div class="section">
        <h2 class="section-title">🔍 PR Previews (${prDirs.length})</h2>
        <div class="card-grid">
            ${prCardsHtml}
        </div>
    </div>

    <div class="info-section">
        <h3>About This Documentation</h3>
        <p>This hub provides access to ManMan API documentation across different versions and development stages:</p>
        <ul>
            <li><strong>Latest Release:</strong> Stable documentation from the main branch</li>
            <li><strong>Release Versions:</strong> Documentation for all published releases</li>
            <li><strong>PR Previews:</strong> Live previews of API changes in active pull requests</li>
        </ul>
        <p><strong>Last updated:</strong> <code>${new Date().toISOString()}</code></p>
    </div>
</body>
</html>`;

    fs.writeFileSync(outputFile, html);
    console.log(`✅ Generated hub index page: ${outputFile}`);
}

// Dynamic PR hub index - discovers PR dirs from filesystem and generates index
function generateDynamicPRHub(siteDir, currentPR, currentPRTitle, outputFile) {
    console.log('🔍 Discovering existing PR preview directories...');

    // Scan the site directory for PR preview folders
    const siteDirs = fs.readdirSync(siteDir);
    const prDirs = siteDirs.filter(dir => dir.startsWith('pr-'));

    console.log(`Found ${prDirs.length} PR preview directories: ${prDirs.join(', ')}`);

    // Always include the current PR
    const currentPRDir = `pr-${currentPR}`;
    if (!prDirs.includes(currentPRDir)) {
        prDirs.push(currentPRDir);
    }

    // Sort PR directories by number (newest first)
    prDirs.sort((a, b) => {
        const numA = parseInt(a.replace('pr-', ''));
        const numB = parseInt(b.replace('pr-', ''));
        return numB - numA;
    });

    console.log(`Including PR directories: ${prDirs.join(', ')}`);

    // Generate PR preview cards HTML
    let prCardsHtml = '';
    for (const prDir of prDirs) {
        const prNumber = prDir.replace('pr-', '');

        let prTitle = 'Loading...';
        const prUrl = `${prDir}/`;

        if (prNumber == currentPR) {
            prTitle = currentPRTitle;
        }

        prCardsHtml += `
                <div class="preview-card pr-preview">
                    <h2 class="preview-title">🔍 PR #${prNumber} Preview</h2>
                    <p><strong>${prTitle}</strong></p>
                    <p>Preview of API changes in pull request #${prNumber}</p>
                    <a href="${prUrl}" class="preview-link">View PR Preview</a>
                </div>`;
    }

    // Generate the complete index.html
    const indexHtml = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ManMan API Documentation Hub</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
            background: #f8fafc;
        }
        .header {
            text-align: center;
            margin-bottom: 3rem;
            padding-bottom: 2rem;
            border-bottom: 2px solid #e2e8f0;
        }
        .section {
            margin-bottom: 3rem;
        }
        .section-title {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #1e293b;
        }
        .preview-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 2rem;
            margin-top: 2rem;
        }
        .preview-card {
            background: white;
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            border: 1px solid #e2e8f0;
        }
        .main-docs {
            border-left: 4px solid #10b981;
        }
        .pr-preview {
            border-left: 4px solid #f59e0b;
        }
        .preview-title {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #1e293b;
        }
        .preview-link {
            display: inline-block;
            background: #3b82f6;
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 500;
            margin-top: 1rem;
        }
        .main-docs .preview-link {
            background: #10b981;
        }
        .pr-preview .preview-link {
            background: #f59e0b;
        }
        .empty-state {
            text-align: center;
            color: #64748b;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>ManMan API Documentation Hub</h1>
        <p>Access the latest API documentation and PR previews</p>
    </div>

    <div class="section">
        <h2 class="section-title">🚀 Latest Release Documentation</h2>
        <div class="preview-grid">
            <div class="preview-card main-docs">
                <h2 class="preview-title">Latest Release Documentation</h2>
                <p>Official API documentation from the latest stable release</p>
                <a href="main/" class="preview-link">View Main Documentation</a>
            </div>
        </div>
    </div>

    <div class="section">
        <h2 class="section-title">🔍 PR Previews (${prDirs.length})</h2>
        <div class="preview-grid">
            ${prCardsHtml || '<div class="empty-state">No PR previews available</div>'}
        </div>
    </div>

    <div style="margin-top: 3rem; padding: 1rem; background: #f1f5f9; border-radius: 8px; font-size: 0.875rem; color: #475569;">
        <strong>Last updated:</strong> ${new Date().toISOString()}<br>
        <strong>Generated by:</strong> OpenAPI Documentation Workflow
    </div>
</body>
</html>`;

    // Write the index.html file
    fs.writeFileSync(outputFile, indexHtml);
    console.log('✅ Generated dynamic index.html with all PR previews');
}

// Dynamic release hub index - discovers both PR and version dirs from filesystem
function generateDynamicReleaseHub(siteDir, outputFile) {
    console.log('🔍 Discovering all version directories...');

    // Scan the site/versions directory for version folders
    let versionDirs = [];
    const versionsPath = path.join(siteDir, 'versions');
    if (fs.existsSync(versionsPath)) {
        versionDirs = fs.readdirSync(versionsPath).filter(dir => {
            // Check if it's a directory and looks like a version (starts with 'v')
            const fullPath = path.join(versionsPath, dir);
            return fs.statSync(fullPath).isDirectory() && dir.startsWith('v');
        });
    }

    console.log(`Found ${versionDirs.length} version directories: ${versionDirs.join(', ')}`);

    // Sort versions (newest first) - simple string sort should work for semantic versions
    versionDirs.sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));

    // Also check for PR directories
    let prDirs = [];
    if (fs.existsSync(siteDir)) {
        const siteDirs = fs.readdirSync(siteDir);
        prDirs = siteDirs.filter(dir => dir.startsWith('pr-'));
        // Sort PR directories by number (newest first)
        prDirs.sort((a, b) => {
            const numA = parseInt(a.replace('pr-', ''));
            const numB = parseInt(b.replace('pr-', ''));
            return numB - numA;
        });
    }

    console.log(`Found ${prDirs.length} PR directories: ${prDirs.join(', ')}`);

    // Generate version history cards HTML
    let versionCardsHtml = '';
    if (versionDirs.length > 0) {
        for (const versionDir of versionDirs) {
            versionCardsHtml += `
                <div class="card version-docs">
                    <h3 class="card-title">📦 ${versionDir}</h3>
                    <p class="card-description">API documentation for release ${versionDir}</p>
                    <a href="versions/${versionDir}/" class="card-link">View Documentation</a>
                </div>`;
        }
    } else {
        versionCardsHtml = '<div class="card"><p class="card-description">No release versions available yet</p></div>';
    }

    // Generate PR preview cards HTML
    let prCardsHtml = '';
    if (prDirs.length > 0) {
        for (const prDir of prDirs) {
            const prNumber = prDir.replace('pr-', '');
            prCardsHtml += `
                <div class="card pr-preview">
                    <h3 class="card-title">🔍 PR #${prNumber} Preview</h3>
                    <p class="card-description">Preview of API changes in pull request #${prNumber}</p>
                    <a href="${prDir}/" class="card-link">View PR Preview</a>
                </div>`;
        }
    } else {
        prCardsHtml = '<div class="card"><p class="card-description">No active PR previews</p></div>';
    }

    // Generate the complete index.html
    const indexHtml = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ManMan API Documentation Hub</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 2rem;
            background: #f8fafc;
        }
        .header {
            text-align: center;
            margin-bottom: 3rem;
            padding-bottom: 2rem;
            border-bottom: 2px solid #e2e8f0;
        }
        .section {
            margin-bottom: 3rem;
        }
        .section-title {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #1e293b;
        }
        .card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 1.5rem;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            border: 1px solid #e2e8f0;
        }
        .main-docs {
            border-left: 4px solid #10b981;
        }
        .pr-preview {
            border-left: 4px solid #f59e0b;
        }
        .version-docs {
            border-left: 4px solid #6366f1;
        }
        .card-title {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #1e293b;
        }
        .card-description {
            color: #64748b;
            margin-bottom: 1.5rem;
            line-height: 1.6;
        }
        .card-link {
            display: inline-block;
            background: #3b82f6;
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 500;
        }
        .main-docs .card-link {
            background: #10b981;
        }
        .pr-preview .card-link {
            background: #f59e0b;
        }
        .version-docs .card-link {
            background: #6366f1;
        }
        .info-section {
            background: #f8fafc;
            border-radius: 8px;
            padding: 1.5rem;
            margin-top: 2rem;
            border: 1px solid #e2e8f0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>ManMan API Documentation Hub</h1>
        <p>Access API documentation for all versions and PR previews</p>
    </div>

    <div class="section">
        <h2 class="section-title">🚀 Current Documentation</h2>
        <div class="card-grid">
            <div class="card main-docs">
                <h3 class="card-title">Latest Release Documentation</h3>
                <p class="card-description">Official API documentation from the latest stable release</p>
                <a href="main/" class="card-link">View Documentation</a>
            </div>
        </div>
    </div>

    <div class="section">
        <h2 class="section-title">📚 Release Versions (${versionDirs.length})</h2>
        <div class="card-grid">
            ${versionCardsHtml}
        </div>
    </div>

    <div class="section">
        <h2 class="section-title">🔍 PR Previews (${prDirs.length})</h2>
        <div class="card-grid">
            ${prCardsHtml}
        </div>
    </div>

    <div class="info-section">
        <h3>About This Documentation</h3>
        <p>This hub provides access to ManMan API documentation across different versions and development stages:</p>
        <ul>
            <li><strong>Latest Release:</strong> Stable documentation from the main branch</li>
            <li><strong>Release Versions:</strong> Documentation for all published releases</li>
            <li><strong>PR Previews:</strong> Live previews of API changes in active pull requests</li>
        </ul>
        <p><strong>Last updated:</strong> <code>${new Date().toISOString()}</code></p>
    </div>
</body>
</html>`;

    // Write the index.html file
    fs.writeFileSync(outputFile, indexHtml);
    console.log(`✅ Updated documentation hub with ${versionDirs.length} versions and ${prDirs.length} PR previews`);
}

// Dynamic cleanup hub index - used when PR is closed to regenerate index without the closed PR
function generateDynamicCleanupHub(siteDir, outputFile) {
    console.log('🔍 Regenerating index after PR cleanup...');

    // Scan the site directory for remaining PR preview folders
    let siteDirs = [];
    if (fs.existsSync(siteDir)) {
        siteDirs = fs.readdirSync(siteDir);
    }
    const prDirs = siteDirs.filter(dir => dir.startsWith('pr-'));

    console.log(`Found ${prDirs.length} remaining PR preview directories: ${prDirs.join(', ')}`);

    // Sort PR directories by number (newest first)
    prDirs.sort((a, b) => {
        const numA = parseInt(a.replace('pr-', ''));
        const numB = parseInt(b.replace('pr-', ''));
        return numB - numA;
    });

    // Generate PR preview cards HTML
    let prCardsHtml = '';
    if (prDirs.length > 0) {
        for (const prDir of prDirs) {
            const prNumber = prDir.replace('pr-', '');

            prCardsHtml += `
                <div class="preview-card pr-preview">
                    <h2 class="preview-title">🔍 PR #${prNumber} Preview</h2>
                    <p><strong>Loading...</strong></p>
                    <p>Preview of API changes in pull request #${prNumber}</p>
                    <a href="${prDir}/" class="preview-link">View PR Preview</a>
                </div>`;
        }
    } else {
        prCardsHtml = '<div class="empty-state">No active PR previews</div>';
    }

    // Generate the complete index.html
    const indexHtml = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ManMan API Documentation Hub</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
            background: #f8fafc;
        }
        .header {
            text-align: center;
            margin-bottom: 3rem;
            padding-bottom: 2rem;
            border-bottom: 2px solid #e2e8f0;
        }
        .section {
            margin-bottom: 3rem;
        }
        .section-title {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #1e293b;
        }
        .preview-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 2rem;
            margin-top: 2rem;
        }
        .preview-card {
            background: white;
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            border: 1px solid #e2e8f0;
        }
        .main-docs {
            border-left: 4px solid #10b981;
        }
        .pr-preview {
            border-left: 4px solid #f59e0b;
        }
        .preview-title {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #1e293b;
        }
        .preview-link {
            display: inline-block;
            background: #3b82f6;
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 500;
            margin-top: 1rem;
        }
        .main-docs .preview-link {
            background: #10b981;
        }
        .pr-preview .preview-link {
            background: #f59e0b;
        }
        .empty-state {
            text-align: center;
            color: #64748b;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>ManMan API Documentation Hub</h1>
        <p>Access the latest API documentation and PR previews</p>
    </div>

    <div class="section">
        <h2 class="section-title">🚀 Latest Release Documentation</h2>
        <div class="preview-grid">
            <div class="preview-card main-docs">
                <h2 class="preview-title">Latest Release Documentation</h2>
                <p>Official API documentation from the latest stable release</p>
                <a href="main/" class="preview-link">View Main Documentation</a>
            </div>
        </div>
    </div>

    <div class="section">
        <h2 class="section-title">🔍 PR Previews (${prDirs.length})</h2>
        <div class="preview-grid">
            ${prCardsHtml}
        </div>
    </div>

    <div style="margin-top: 3rem; padding: 1rem; background: #f1f5f9; border-radius: 8px; font-size: 0.875rem; color: #475569;">
        <strong>Last updated:</strong> ${new Date().toISOString()}<br>
        <strong>Generated by:</strong> OpenAPI Documentation Workflow (cleanup)
    </div>
</body>
</html>`;

    // Write the index.html file
    fs.writeFileSync(outputFile, indexHtml);
    console.log(`✅ Regenerated index.html after cleanup, showing ${prDirs.length} remaining PR previews`);
}

// Static main hub index - static version for main branch deployment
function generateStaticMainHub(outputFile) {
    const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ManMan API Documentation Hub</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 2rem;
            background: #f8fafc;
        }
        .header {
            text-align: center;
            margin-bottom: 3rem;
            padding-bottom: 2rem;
            border-bottom: 2px solid #e2e8f0;
        }
        .section {
            margin-bottom: 3rem;
        }
        .section-title {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #1e293b;
        }
        .card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 1.5rem;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            border: 1px solid #e2e8f0;
        }
        .main-docs {
            border-left: 4px solid #10b981;
        }
        .pr-preview {
            border-left: 4px solid #f59e0b;
        }
        .version-docs {
            border-left: 4px solid #6366f1;
        }
        .card-title {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #1e293b;
        }
        .card-description {
            color: #64748b;
            margin-bottom: 1.5rem;
            line-height: 1.6;
        }
        .card-link {
            display: inline-block;
            background: #3b82f6;
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 500;
        }
        .main-docs .card-link {
            background: #10b981;
        }
        .pr-preview .card-link {
            background: #f59e0b;
        }
        .version-docs .card-link {
            background: #6366f1;
        }
        .info-section {
            background: #f8fafc;
            border-radius: 8px;
            padding: 1.5rem;
            margin-top: 2rem;
            border: 1px solid #e2e8f0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>ManMan API Documentation Hub</h1>
        <p>Access API documentation for all versions and PR previews</p>
    </div>

    <div class="section">
        <h2 class="section-title">🚀 Current Documentation</h2>
        <div class="card-grid">
            <div class="card main-docs">
                <h3 class="card-title">Latest Release Documentation</h3>
                <p class="card-description">Official API documentation from the latest stable release</p>
                <a href="main/" class="card-link">View Documentation</a>
            </div>
        </div>
    </div>

    <div class="section">
        <h2 class="section-title">🔍 PR Previews</h2>
        <div class="card-grid" id="pr-previews">
            <div class="card">
                <p class="card-description">PR previews will appear here when pull requests are opened</p>
            </div>
        </div>
    </div>

    <div class="section">
        <h2 class="section-title">📚 Version History</h2>
        <div class="card-grid" id="version-history">
            <div class="card">
                <p class="card-description">Historical versions will appear here as releases are published</p>
            </div>
        </div>
    </div>

    <div class="info-section">
        <h3>About This Documentation</h3>
        <p>This hub provides access to ManMan API documentation across different versions and development stages:</p>
        <ul>
            <li><strong>Latest Release:</strong> Stable documentation from the main branch</li>
            <li><strong>PR Previews:</strong> Live previews of API changes in active pull requests</li>
            <li><strong>Version History:</strong> Documentation for all released versions</li>
        </ul>
        <p><strong>Last updated:</strong> <code>${new Date().toISOString()}</code></p>
    </div>
</body>
</html>`;

    fs.writeFileSync(outputFile, html);
    console.log(`✅ Generated static main hub index: ${outputFile}`);
}

// Main function
function main() {
    const args = process.argv.slice(2);
    
    if (args.length < 2) {
        console.error('Usage: node generate-docs-html.js <type> <output-file> [options]');
        process.exit(1);
    }

    const [type, outputFile, ...options] = args;

    switch (type) {
        case 'pr-index':
            if (options.length < 4) {
                console.error('Usage: pr-index <output-file> <pr-number> <pr-title> <branch> <sha>');
                process.exit(1);
            }
            generatePRIndex(options[0], options[1], options[2], options[3], outputFile);
            break;

        case 'release-index':
            if (options.length < 2) {
                console.error('Usage: release-index <output-file> <version> <sha>');
                process.exit(1);
            }
            generateReleaseIndex(options[0], options[1], outputFile);
            break;

        case 'main-index':
            generateMainIndex(outputFile);
            break;

        case 'hub-index':
            // Options are arrays of PR dirs and version dirs
            const prDirs = [];
            const versionDirs = [];
            let inVersions = false;
            
            for (const option of options) {
                if (option === '--versions') {
                    inVersions = true;
                    continue;
                }
                if (inVersions) {
                    versionDirs.push(option);
                } else {
                    prDirs.push(option);
                }
            }
            
            generateHubIndex(prDirs, versionDirs, outputFile);
            break;

        case 'dynamic-pr-hub':
            if (options.length < 3) {
                console.error('Usage: dynamic-pr-hub <output-file> <site-dir> <current-pr> <current-pr-title>');
                process.exit(1);
            }
            generateDynamicPRHub(options[0], options[1], options[2], outputFile);
            break;

        case 'dynamic-release-hub':
            if (options.length < 1) {
                console.error('Usage: dynamic-release-hub <output-file> <site-dir>');
                process.exit(1);
            }
            generateDynamicReleaseHub(options[0], outputFile);
            break;

        case 'dynamic-cleanup-hub':
            if (options.length < 1) {
                console.error('Usage: dynamic-cleanup-hub <output-file> <site-dir>');
                process.exit(1);
            }
            generateDynamicCleanupHub(options[0], outputFile);
            break;

        case 'static-main-hub':
            generateStaticMainHub(outputFile);
            break;

        default:
            console.error(`Unknown type: ${type}`);
            process.exit(1);
    }
}

if (require.main === module) {
    main();
}