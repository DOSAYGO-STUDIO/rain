#!/usr/bin/env node
import crypto from 'crypto';
import chalk from 'chalk';
import { execSync } from 'child_process';

function calculateHash(input, hashMethod) {
    let hash;
    switch (hashMethod) {
        case 'rainsum':
            hash = execSync(`echo -n "${input}" | ./rainsum -a rainstorm -s 512`, { encoding: 'utf8' }).split(' ')[0];
            break;
        case 'shasum':
            hash = execSync(`echo -n "${input}" | shasum -a 512`, { encoding: 'utf8' }).split(' ')[0];
            break;
        default:
            let shasum = crypto.createHash('sha512');
            shasum.update(input);
            hash = shasum.digest('hex');
            break;
    }
    return hash;
}

function highlightMatchingCharacters(prevHash, currHash, nextHash) {
    let highlighted = '';
    for (let i = 0; i < currHash.length; i++) {
        if (prevHash[i] === currHash[i] || currHash[i] === nextHash[i]) {
            highlighted += chalk.bold.rgb(50, 205, 50)(currHash[i]);  // Bold Lime color
        } else {
            highlighted += chalk.black(currHash[i]);  // Cyan color
        }
    }
    return highlighted;
}

let input = '';
let n = process.argv[2] || '-';
let hashMethod = process.argv[3] || 'shasum';  // default to 'shasum'
let prevHash = '';
let currHash = calculateHash(input, hashMethod);
let nextHash;

if (n === '-') {
    // Infinite loop
    while (true) {
        nextHash = calculateHash(currHash, hashMethod);
        const highlighted = prevHash ? highlightMatchingCharacters(prevHash, currHash, nextHash) : currHash;
        console.log(highlighted);
        prevHash = currHash;
        currHash = nextHash;
    }
} else {
    // Loop for n times
    for (let i = 0; i < n; i++) {
        nextHash = calculateHash(currHash, hashMethod);
        const highlighted = prevHash ? highlightMatchingCharacters(prevHash, currHash, nextHash) : currHash;
        console.log(highlighted);
        prevHash = currHash;
        currHash = nextHash;
    }
}

