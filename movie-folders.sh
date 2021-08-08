#!/bin/bash

#
#   MOVIE MOVER 
# 
#   A script to move movies into their own folders
#

# Location of your movies
src=/volume1/Media/movies

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

#
#   CLEAN EMPTY FOLDERS
#
echo ========== SCRUB EMPTY FOLDERS ==========
folders=($(find $src -maxdepth 1 -mindepth 1 -type d | grep -v "/$" | grep -v "@eaDir"))

for folder in ${folders[*]}; do
  size=$(du -d0 $folder | awk '{print $1}')
  # Only scrub folders with not much in them
  if [ $size -lt 90000 ]; then
    echo [SCRUB ] $(basename $folder) \($size KB\)
    # really delete it
    rm -rf $folder
  else
    echo [ SKIP ] $(basename $folder) \($size KB\)
  fi
done
