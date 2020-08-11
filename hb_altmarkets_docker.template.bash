# hb_altmarkets_docker.bash
# 
# OPTIONS:
# hb_altmarkets_docker.sh BUILD        # don't need to specify instance number here.
# hb_altmarkets_docker.sh START X      # Where X is the hummingbot instance - can be any number but might as well start from 1 right?
#                                   # Can run as many instances as you like by repeating the command with new number
# hb_altmarkets_docker.sh DEL X        # Where X is the MAX hummingbot instance - it will go through all instances up to this number and delete logs/data but NOT conf files


# Change this to the path where you clones hummingbot to
HUMMINGBOT_DIRECTORY=/somedir/hummingbot


NUM=1
if [ ! -z $2 ]
then
	NUM=$2
fi

BUILD_NAME=hummingbot1
INSTANCE_NAME=hummingbot-instance$NUM
DIR_NAME=hummingbot_files$NUM


cd $HUMMINGBOT_DIRECTORY

if [ ! -z $1 ] && [ $1 == 'BUILD' ] ; then
	docker image rm --force $BUILD_NAME
	docker build -t $BUILD_NAME .
	exit 0
fi

cd ./installation/docker-commands/hummingbot_files/

if [ ! -z $1 ] && [ $1 == 'DEL' ] && [ ! -z $2 ]; then
	echo "Deleting all logs/data for bots."
	for i in $(seq 1 $2); do
		echo "Deleting bot $i"
		rm -r hummingbot_files$i/hummingbot_logs/* && \
		rm -r hummingbot_files$i/hummingbot_data/*
		docker container rm hummingbot-instance$i
	done
	exit 0
fi

if [ ! -z $1 ] && [ $1 == 'START' ] && [ ! -z $2 ]; then
	mkdir -p $DIR_NAME/hummingbot_conf && \
	mkdir $DIR_NAME/hummingbot_logs && \
	mkdir $DIR_NAME/hummingbot_data && \
	mkdir $DIR_NAME/hummingbot_scripts

	docker run -it \
	--network host \
	--name $INSTANCE_NAME \
	--mount "type=bind,source=$(pwd)/$DIR_NAME/hummingbot_conf,destination=/conf/" \
	--mount "type=bind,source=$(pwd)/$DIR_NAME/hummingbot_logs,destination=/logs/" \
	--mount "type=bind,source=$(pwd)/$DIR_NAME/hummingbot_data,destination=/data/" \
	--mount "type=bind,source=$(pwd)/$DIR_NAME/hummingbot_scripts,destination=/scripts/" \
	$BUILD_NAME || \
	# docker start -i -a $INSTANCE_NAME
	docker container rm $INSTANCE_NAME && \
	docker run -it \
	--network host \
	--name $INSTANCE_NAME \
	--mount "type=bind,source=$(pwd)/$DIR_NAME/hummingbot_conf,destination=/conf/" \
	--mount "type=bind,source=$(pwd)/$DIR_NAME/hummingbot_logs,destination=/logs/" \
	--mount "type=bind,source=$(pwd)/$DIR_NAME/hummingbot_data,destination=/data/" \
	--mount "type=bind,source=$(pwd)/$DIR_NAME/hummingbot_scripts,destination=/scripts/" \
	$BUILD_NAME
fi