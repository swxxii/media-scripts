#!/bin/bash

#
#   MOVIE MOVER 
# 
#   Note: If running from docker, paths must be accessible by the container.
#

# Completed downloads path
src=/volume1/Media/downloads/complete

# Destination for movies
dest=/volume1/Media/movies

# Recycle Bin location
recy=/volume1/Media/downloads/recycled

# Threshold - only move files bigger than X megabytes
threshold=900

# separate by newline
export IFS=$'\n'

# get list of video files, exclusing regex and strings often that appear in episodes
files=$(find $src -type f | egrep "\.(mkv|mp4|avi|mpeg4|mpg|divx)$" | egrep -vi "S[0-9]{1,2}E[0-9]{1,2}?|[0-9]{1,2}x[0-9]{1,2}|Season|HorribleSubs")

# check each file
for file in ${files[*]}; do
  echo Checking: $file

  # extract size in megabytes
  size=$(ls -l $file | awk '{print $5}')
  size=$(expr $size / 1048576)

  if [ $size -gt $threshold ]; then
    echo Moving: $(basename $file) \($size MB\)
    mv $file $dest
    # also move subs
    mv "${file%.*}.srt" $dest 2>/dev/null
  else
    echo Skipping: $(basename $file) \($size MB\)
  fi
done

#
#   CLEAN EMPTY FOLDERS
#
folders=($(find $src -maxdepth 1 -mindepth 1 -type d | grep -v "/$"))

for folder in ${folders[*]}; do
  size=$(du -d0 $folder | awk '{print $1}')
  # Only move folders with not much in them
  if [ $size -lt 90000 ]; then
    echo Cleaning folder: $(basename $folder) \($size KB\)
    # uncomment next line to RECYCLE
    mv $folder $recy
    # uncomment next line to DELETE
    #rm -rf $folder
  else
    echo Leaving: $(basename $folder) \($size KB\)
  fi
done
