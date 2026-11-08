#!/usr/bin/env node
import chalk from 'chalk';
import fs from 'fs';
import {execSync, exec as callbackExec} from 'child_process';
import util from 'util';
const exec = util.promisify(callbackExec);

// Generate files of various sizes
async function generateFiles() {
    for (let size = 1; size <= 8; size++) {
        // Calculate size in bytes
        let bytes = Math.pow(10, size);

        // Generate a file with `dd`
        execSync(`dd if=/dev/urandom of=input${size} bs=${bytes} count=1 > /dev/null 2>&1`);
    }
}

// Define your test inputs here
const inputs = ["input1", "input2", "input3", "input4", "input5", "input6", "input7", "input8"];

async function timeExecution(command) {
    const start = process.hrtime.bigint();
    await exec(command);
    const end = process.hrtime.bigint();
    return end - start;
}

async function main() {
    await generateFiles();

    console.log(chalk.bold("\nRain hash functions C++ vs Node/WASM benchmark:\n"));

    const title = `${'Test Input & Size (bytes)'.padEnd(31)} ${'Run'.padStart(5)} ${'C++ Version'.padStart(18)} ${'WASM Version'.padStart(18)} ${'Fastest'.padStart(16)}`;
    console.log(chalk.bold(title));

    // Run each test three times
    for (let run = 1; run <= 3; run++) {
        for (let input of inputs) {
            // Get input file size
            const stats = fs.statSync(input);
            const fileSizeInBytes = stats.size.toLocaleString();

            // Running and timing the CPP version
            const time_cpp = await timeExecution(`./rainsum ${input} > /dev/null 2>&1`);

            // Running and timing the NodeJS version
            const time_js = await timeExecution(`node ./js/rainsum.mjs ${input} > /dev/null 2>&1`);

            // Calculate which is faster
            let faster;
            let color;
            if (time_cpp < time_js) {
                faster = Number(time_js / time_cpp).toFixed(2) + "x (C++ wins!)";
                color = chalk.green;
            } else {
                faster = Number(time_cpp / time_js).toFixed(2) + "x (NodeJS wins!)";
                color = chalk.blue;
            }

            const row = `${input} (${fileSizeInBytes} bytes)`.padEnd(35) + `${run.toString().padEnd(4)} ${time_cpp.toLocaleString().padStart(14)} ns ${time_js.toLocaleString().padStart(14)} ns ${faster.padStart(22)}`;
            console.log(color(row));
        }
    }

    // Teardown step: delete generated files
    for (let input of inputs) {
        try {
            fs.unlinkSync(input);
        } catch (err) {
            console.error(`Error while deleting ${input}. ${err}`);
        }
    }
}

main();

