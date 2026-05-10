#!/bin/bash

initRun=1
reps=1


mkdir mn_results


for ((run=$initRun;run<$initRun+$reps; run+=1))
do
    for placement in router hosts; do
		mkdir ./mn_results/$placement
        for type in 1 2 3; do
			sudo mn -c
            mkdir ./mn_results/$placement/$type
			mkdir ./mn_results/$placement/$type/$run
			sudo python3 topo.py --placement $placement --type $type
			sudo mv *.csv ./mn_results/$placement/$type/$run
			sudo mv *.txt ./mn_results/$placement/$type/$run
        done
    done
done

