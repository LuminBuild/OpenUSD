#!/usr/bin/env python
#
# Copyright 2019 Pixar
#
# Licensed under the terms set forth in the LICENSE.txt file available at
# https://openusd.org/license.
#

from __future__ import print_function

from tempfile import mkdtemp
from argparse import ArgumentParser
from sys import exit, stdout 
from os import listdir, mkdir, getcwd, chdir, rename, access, W_OK
from os.path import abspath, basename, join, splitext, isfile, dirname, exists
from subprocess import call
from shutil import rmtree, copyfile
from difflib import unified_diff

# -----------------------------------------------------------------------------
# Validation functions.
# This section contains code that will gather/report diffs between the generated
# code and the installed files as well as installing generating files which
# pass validation.
# -----------------------------------------------------------------------------
def _compareFiles(installedFiles, generatedFiles, configuration):
    failOnDiff = configuration[VALIDATE]

    if len(installedFiles) != len(generatedFiles):
        installedNames = set(map(basename, installedFiles))
        generatedNames = set(map(basename, generatedFiles))

        if (generatedNames - installedNames):
            exit('*** Unknown files generated, please add them to the list of '
                 'base files names in hdPrmanGenParsers.py')

        exit('*** Missing files:\n' + '\n'.join(installedNames - generatedNames))

    diffs = {}
    for i in range(0, len(installedFiles)):
        installedExists = isfile(installedFiles[i])
        generatedExists = isfile(generatedFiles[i])

        if installedExists and not generatedExists:
            diffs[basename(installedFile.name)] = "File not generated"
            continue

        if not installedExists and generatedExists:
            diffs[basename(installedFiles[i])] = "Installed file does not exist"
            continue

        with open(installedFiles[i], 'r') as installedFile,\
             open(generatedFiles[i], 'r') as generatedFile:
            
            installedContent = installedFile.read()
            generatedContent = generatedFile.read()

            if installedContent != generatedContent:
                diff = '\n'.join(unified_diff(installedContent.split('\n'),
                                              generatedContent.split('\n'),
                                              'Source ' + installedFile.name,
                                              'Generated ' + generatedFile.name))
                diffs[basename(installedFile.name)] = diff

    if diffs and failOnDiff:
        exit('*** Differing Generated Files:\n' + '\n'.join(diffs.values()))

    return diffs

def _copyGeneratedFiles(installedFiles, generatedFiles, diffs):
    baseNames = [basename(installedFile) for installedFile in installedFiles]
    for baseName, generatedFile, installedFile in zip(baseNames, 
                                                      generatedFiles, 
                                                      installedFiles):
        if baseName in diffs:
            print('Changed: ' + baseName)
            print(diffs[baseName])
            if isfile(installedFile) and not access(installedFile, W_OK):
                print('Cannot author ' + installedFile + ', (no write access).')
            else:
                copyfile(generatedFile, installedFile) 
        else:
            print('Unchanged: ' + baseName)

# -----------------------------------------------------------------------------
# Code generation functions.
# This section contains the code that will actually generate the C++ source
# and headers from the yy/ll source files as well as the code which will
# curate the generated code.
# -----------------------------------------------------------------------------
def _runBisonAndFlexCommands(configuration):
    # build up collections of all relevant files, these include 
    # yy/ll source files, as well as the generated C++ header
    # and source files.
    srcDir   = configuration[SRC_DIR]
    destDir  = configuration[DEST_DIR]
    bases    = configuration[BASES]

    bisonFiles      = [join(srcDir, base + '.yy') for base in bases] 
    flexFiles       = [join(srcDir, base + '.ll') for base in bases]
    bisonGenSources = [join(destDir, base + '.tab.cpp') for base in bases]
    bisonGenHeaders = [join(destDir, base + '.tab.hpp') for base in bases]
    flexGenSources  = [join(destDir, base + '.lex.cpp') for base in bases]

    sourceFiles    = bisonFiles + flexFiles
    generatedFiles = bisonGenHeaders + bisonGenSources + flexGenSources

    # generate all components of a flex/bison command, these
    # include the desired executables, flag settings 
    bisonFlags = lambda base: ['-d', '-p', base + 'Yy', '-o']
    flexFlags  = lambda base: ['-P'+ base + "Yy", '-t']  

    bisonExecutable = configuration[BISON_EXE]
    flexExecutable  = configuration[FLEX_EXE]
    
    bisonCommand = lambda index: ([bisonExecutable]
                                  + bisonFlags(base) 
                                  + [bisonGenSources[index]] 
                                  + [bisonFiles[index]])

    flexCommand  = lambda index: ([flexExecutable] 
                                  + flexFlags(base)
                                  + [flexFiles[index]])
    
    for index, base in enumerate(bases):
        print('Running bison on %s' % (base + '.yy'))
        call(bisonCommand(index))

        print('Running flex on %s' % (base + '.ll'))
        with open(flexGenSources[index], 'w') as outputFile:
            call(flexCommand(index), stdout=outputFile)

    # prepend license header to all generated files.
    licenseText = '\n'.join([
    "//"
    , "// Copyright 2019 Pixar"
    , "//"
    , "// Licensed under the terms set forth in the LICENSE.txt file available at"
    , "// https://openusd.org/license."
    , "//\n"])

    for generatedFile in generatedFiles:
        with open(generatedFile, 'r') as f:
            lines = f.read()
        with open(generatedFile, 'w') as f:
            f.write(licenseText)
            f.write(lines)

    return sourceFiles, generatedFiles

def _canonicalizeFiles(sourceFiles, generatedFiles):
    PXR_PREFIX_PATH = 'hdPrman'

    # by default, bison will output hpp header files, we don't want this
    # as it goes against our convention of .h for headers. More recent
    # versions of bison support this option directly.
    #
    # We also need to update the paths in the generated #line directives
    # so we can easily diff the generated and installed files.

    # 'renamed' represents the renamed files on disk, whereas the identifiers
    # are altered paths that will be used in #line directives in the source
    renamed = list(generatedFiles)
    identifiers = list(generatedFiles)

    # rename hpp files to h, also update our index of renamed files
    # and identifiers(these will be used when scrubbing the files' contents)
    for index, fileName in enumerate(generatedFiles):
        if 'hpp' in fileName:
            newName = fileName.replace('.hpp', '.h')
            rename(fileName, newName)
            renamed[index] = newName
            identifiers[index] = newName

    # identifiers includes the sourceFiles(yy,ll files) because 
    # they are also referred to in line directives
    identifiers += sourceFiles
    for index, fileName in enumerate(list(renamed + sourceFiles)):
        if '/' in fileName:
            identifiers[index] = join(PXR_PREFIX_PATH, basename(fileName))

    # create a list of pairs, representing the things to replace in our
    # generated files
    replacements = [] 
    for index, fileName in enumerate(list(generatedFiles+sourceFiles)):
        oldFileName = fileName
        newFileName = identifiers[index]
        replacements.append((oldFileName, newFileName))

    for renamedFile in renamed:
        print('Canonicalizing ' + basename(renamedFile))

        with open(renamedFile, 'r+') as inputFile:
            data = inputFile.read()
            
            # find and replace all generated file names
            print('... Fixing line directives')
            for oldFileName, newFileName in replacements:
                data = data.replace(oldFileName, newFileName)

            # flex versions older than 2.6 emit the register keyword
            # which is no longer supported as of C++17. To support
            # these versions, we manually strip 'register' from each
            # .lex.cpp file. This is hacky, since it could affect 
            # hand-written parser code that uses the word "register".
            # In practice, none of our parser code does this.
            #
            # XXX: Remove this when we stop supporting older flex versions
            if renamedFile.endswith('.lex.cpp'):
                print('... Removing register keyword')
                data = data.replace("register ", "")
            
            # we seek to 0 and truncate as we intend 
            # to overwrite the existing data in the file
            inputFile.seek(0)
            inputFile.write(data)
            inputFile.truncate()

    return renamed

# -----------------------------------------------------------------------------
# Configuration info.
# This section of code discerns all the necessary info the run the parser
# and lexical analyzer generators over the source files.
# -----------------------------------------------------------------------------
def _parseArguments():
    parser = ArgumentParser(description='Generate Ascii File Parsers for HdPrman')
    parser.add_argument('--srcDir', required=False, default=getcwd(),
                        help='The source directory.')
    parser.add_argument('--bison', required=True, 
                        help='The location of the bison executable to be used.')
    parser.add_argument('--flex', required=True,                         
                        help='The location of the flex executable to be used.')
    parser.add_argument('--validate', action='store_true',
                        help='Verify that the source files are unchanged.')
    parser.add_argument('--bases', nargs='+',
                        help='Base file identifiers used for generation.')
    return parser.parse_args()

# Configuration constants
DEST_DIR   = 0
SRC_DIR    = 1
VALIDATE   = 2
BASES      = 3
BISON_EXE  = 4
FLEX_EXE   = 5

def _getConfiguration():
    arguments = _parseArguments()

    config = { VALIDATE  : arguments.validate,
               SRC_DIR   : arguments.srcDir,
               DEST_DIR  : mkdtemp(),
               BISON_EXE : arguments.bison,
               FLEX_EXE  : arguments.flex,
               BASES     : arguments.bases }
               
    # Ensure all optional arguments get properly populated
    if not arguments.bases:
        allFiles = listdir(arguments.srcDir)
        validExts = ['.yy', '.ll']
        relevantFiles = [f for f in allFiles if splitext(f)[1] in validExts]
        bases = list(set(map(lambda f: splitext(f)[0], relevantFiles)))

        if not bases:
            exit('*** Unable to find source files for parser. Ensure that they '
                 'are in the source directory(--srcDir). If unspecified, the '
                 'source directory is assumed to be the current directory.')

        config[BASES] = bases 

    return config

# -----------------------------------------------------------------------------

def _printSection(sectionInfo):
    print('+-------------------------------------------------+')
    print(sectionInfo)
    print('+-------------------------------------------------+')

if __name__ == '__main__':
    configuration = _getConfiguration()

    _printSection('Running flex and bison on sources')
    sourceFiles, generatedFiles = _runBisonAndFlexCommands(configuration)

    _printSection('Canonicalizing generated files')
    generatedFiles = _canonicalizeFiles(sourceFiles, generatedFiles)
    
    diffSectionMsg = 'Checking for diffs'
    if configuration[VALIDATE]:
        diffSectionMsg = diffSectionMsg + '(validation on)'

    _printSection(diffSectionMsg)
    installedFiles = [join(configuration[SRC_DIR], basename(f)) 
                      for f in generatedFiles]

    diffs = _compareFiles(installedFiles, generatedFiles, configuration)
    _copyGeneratedFiles(installedFiles, generatedFiles, diffs) 
    # If validation passed, clean up the generated files
    rmtree(configuration[DEST_DIR])
