#!/bin/bash

#
#   MOVIE MOVER 
# 
#   A script to move movies into their own folders
#   Requirements: bash, find, mv, du
#

# Location of your movies
src=/path/to/movies

# separate by newline
export IFS=$'\n'

# get list of video files with common extensions
files=$(find $src -maxdepth 1 -type f | egrep "\.(mkv|mp4|avi|mpeg4|mpg|divx)$" )
# minus 1 off as it counts the trailing newline
count=`expr ${#files[@]} - 1`

echo ========== MOVE MOVIES INTO FOLDERS ==========
echo [ INFO ] Found $count movie files.

# process each movie file
for file in ${files[*]}; do
  echo [START ] $file
  # get filename without extension
  bn="$(basename $file)"
  # construct new folder names
  newf="${bn%.*}"
  newsrc=$src/$newf
  # make new folder
  echo [ DIR  ] $newsrc 
  mkdir "$newsrc"
  # move the files
  echo [ MOVE ] $bn.*    
  find $src -wholename "${file%.*}.*" -exec mv '{}' $newsrc \;
  echo [ END  ] Finished.
done

# Cleaning up small/empty leftover folders is handled separately by
# tools/prune-small-dirs.py, which lists candidates with sizes and only
# deletes after you confirm. (This script used to rm -rf folders under a
# size threshold here with no confirmation — removed as unsafe.)
