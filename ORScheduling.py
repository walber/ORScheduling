# coding=utf-8
import csv
import datetime
from Numberjack import *
from json2html import *


def load_csv(file_name):
    with open(file_name, 'rb') as csvfile:
        dialect = csv.Sniffer().sniff(csvfile.read(1024))
        csvfile.seek(0)
        reader = csv.DictReader(csvfile, dialect=dialect)
        rowDictList = []

        for row in reader:
          rowDictList.append({f:row[f] for f in reader.fieldnames})

        return {'headers': reader.fieldnames, 'rows': rowDictList}


def tableAsDictOfDict(file_name):
    table = load_csv(file_name)
    pk = table['headers'][0]
    headers = table['headers'][1:]

    return {a[pk] : {h : a[h] for h in headers} for a in table['rows']}


class ORS(object):

    def __init__(self, param):
        self.doctors = tableAsDictOfDict(param['doctors_csv'])
        self.doctsAvailability = tableAsDictOfDict(param['doctorsAvailability_csv'])
        self.roomsAvailability = tableAsDictOfDict(param['roomsAvailability_csv'])
        self.specialities = tableAsDictOfDict(param['specialities_csv'])
        self.surgeries = tableAsDictOfDict(param['surgeries_csv'])
        self.days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        self.C_MAX = Variable(0, 720, 'C_MAX')

        self.main_scruct = dict()
        for day in self.days:
            self.main_scruct[day] = dict()
            for room in self.roomsAvailability.keys():
                if self.roomsAvailability[room][day] == '1':
                    self.main_scruct[day][room] = dict()
                    for doc in self.doctors:
                        self.main_scruct[day][room][doc] = list()
                        for surg in self.surgeries:
                            s_var = (surg, Variable('surg'))
                            self.main_scruct[day][room][doc].append(s_var)


    #
    # Prints the step 1 solution schedule.
    #
    def print_solution_step1(self):

        for day in self.main_scruct:
            for room in self.main_scruct[day]:
                for doc in self.main_scruct[day][room]:
                    for surg, var in self.main_scruct[day][room][doc]:
                        if var.get_value() == 1:
                            print("Day:{} - Room:{} - Doc:{} - Surg:{}".format(day, room, doc, surg))

    #
    # Prints the step 1 solution statistics.
    #
    def print_stats(self):

        spec_count = dict()
        for day in self.main_scruct:
            for room in self.main_scruct[day]:
                for doc in self.main_scruct[day][room]:
                    for surg, var in self.main_scruct[day][room][doc]:
                        if var.get_value() == 1:
                            doc_spec = self.doctors[doc]['ID_Speciality']
                            if doc_spec not in spec_count:
                                spec_count[doc_spec] = 1
                            else:
                                spec_count[doc_spec] += 1

        out = ''
        total = 0
        for s in spec_count:
            total += spec_count[s]
            spec_name = self.specialities[s]['Speciality']
            out += '{}: {}\n'.format(spec_name, spec_count[s])

        out += '\nTotal: {}'.format(total)
        print(out)


    #
    # Constraint 0
    # All var surgeries whose speciality has suspension rate over 0.3
    # will not be scheduled.
    #
    def constraint_0(self):

        var_list = list()
        for day in self.main_scruct:
            for room in self.main_scruct[day]:
                for doc in self.main_scruct[day][room]:
                    for (surg, var) in self.main_scruct[day][room][doc]:
                        if self.surgeries[surg]['Priority'] == '3':
                            surg_spec = self.surgeries[surg]['ID_Speciality']
                            rate = float(self.specialities[surg_spec]['Suspension_rate'])
                            if rate > 0.3:
                                var_list.append(var)

        yield Sum(var_list) == 0


    #
    # Constraint 1
    # Defines the maximal doctors' available daily time.
    #
    def constraint_1(self):

        for day in self.main_scruct:
            doc_vars = dict()
            for room in self.main_scruct[day]:
                for doc in self.main_scruct[day][room]:
                    if doc not in doc_vars:
                       doc_vars[doc] = list()

                    doc_spec = self.doctors[doc]['ID_Speciality']
                    duration = int(self.specialities[doc_spec]['Duration'])

                    for (surg, var) in self.main_scruct[day][room][doc]:
                        surg_spec = self.surgeries[surg]['ID_Speciality']
                        if surg_spec == doc_spec:
                            doc_vars[doc].append(var * duration)

            for doc in doc_vars:
                max_daily_time = int(self.doctors[doc]['Tmaxd'])
                yield Sum(doc_vars[doc]) <= max_daily_time


    #
    # Constraint 2
    # Defines the maximal doctors' available week time.
    #
    def constraint_2(self):

        doc_vars = dict()
        for day in self.main_scruct:
            for room in self.main_scruct[day]:
                for doc in self.main_scruct[day][room]:
                    if doc not in doc_vars:
                       doc_vars[doc] = list()

                    doc_spec = self.doctors[doc]['ID_Speciality']
                    duration = int(self.specialities[doc_spec]['Duration'])

                    for (surg, var) in self.main_scruct[day][room][doc]:
                        surg_spec = self.surgeries[surg]['ID_Speciality']
                        if surg_spec == doc_spec:
                            doc_vars[doc].append(var * duration)

        for doc in doc_vars:
            weekly_time = int(self.doctors[doc]['Tmaxw'])
            yield Sum(doc_vars[doc]) <= weekly_time

    #
    # Constraint 3
    # Assigns to zero the row invalid vars (Invalid (doc, surg) association)
    #
    def constraint_3(self):

        var_list = list()
        for day in self.main_scruct:
            for room in self.main_scruct[day]:
                for doc in self.main_scruct[day][room]:
                    doc_spec = self.doctors[doc]['ID_Speciality']
                    for (surg, var) in self.main_scruct[day][room][doc]:
                        surg_spec = self.surgeries[surg]['ID_Speciality']
                        if surg_spec != doc_spec:
                            var_list.append(var)

        yield Sum(var_list) == 0

    #
    # Constraint 4
    # A Surgery can be scheduled only once. (hard constraint)
    #
    def constraint_4(self):

        col = dict()
        for i, surg in enumerate(self.surgeries):
            col[i] = list()
            for day in self.main_scruct:
                for room in self.main_scruct[day]:
                    for doc in self.main_scruct[day][room]:
                        surg, var = self.main_scruct[day][room][doc][i]
                        col[i].append(var)

        for i in col:
            yield Sum(col[i]) <= 1

    #
    # Constraint 5
    # Each room can be opened for only 720 minutes (12 hours) a day.
    #
    def constraint_5(self):

        for day in self.main_scruct:
            for room in self.main_scruct[day]:
                room_vars = list() 
                for doc in self.main_scruct[day][room]:
                    for _, var in self.main_scruct[day][room][doc]:
                        spec = self.doctors[doc]['ID_Speciality']
                        duration = int(self.specialities[spec]['Duration'])
                        room_vars.append(var * duration)

                yield Sum(room_vars) <= 720

    #
    # First model:
    # The vars searched here defines the surgeries matches for
    # (day, room, doctor) tuples. Each var is mapped to a uniq surgery.
    # 
    #
    def model_1(self):

        var_list = list()
        for day in self.main_scruct:
             for room in self.main_scruct[day]:
                 for doc in self.main_scruct[day][room]:
                     for (surg, var) in self.main_scruct[day][room][doc]:
                         var_list.append(var)

        model = Model(
            list(self.constraint_0()),
            list(self.constraint_1()),
            list(self.constraint_2()),
            list(self.constraint_3()),
            list(self.constraint_4()),
            list(self.constraint_5())
        )

        #
        # Objective function: maximize the total sum of variables.
        #
        model.add(Maximize(Sum(var_list)))
        return model


###################################[part 2]#####################################

    #
    # Generates a HTML file with the surgeries scheduled.
    #
    def gen_scheduling_file(self, operations):
    
        daily_ops = dict()
        day_time = datetime.datetime(year=2017, month=1, day=1, hour=7)
        for (day, room, doc, surg, task) in operations:
            if day not in daily_ops:
                daily_ops[day] = dict()

            if room not in daily_ops[day]:
                daily_ops[day][room] = list()

            minute_offset = task.get_value()
            delta = day_time + datetime.timedelta(minutes=minute_offset)
            delta_minutes = "{:0>2}".format(delta.minute)
            delta_hour = "{:0>2}".format(delta.hour)
            doctor = dict(self.doctors[doc])
            surgery = dict(self.surgeries[surg])

            doctor.pop('ID_Speciality', None)
            doctor.pop('Tmaxw', None)
            doctor.pop('Tmaxd', None)
            surgery.pop('ID_Speciality', None)

            daily_ops[day][room].append({
                'Doctor': doctor,
                'Surgery': surgery,
                'Time': "{}:{}".format(delta_hour, delta_minutes)
            })

        with open('Scheduling.html', 'w') as f:
            f.write(json2html.convert(json = daily_ops))


    #
    # A doctor is able to attend only one surgery at time.
    #
    def constraint_6(self, operations):

        doc_tasks = dict()
        for (day, _, doc, _, task) in operations:
            if day not in doc_tasks:
                doc_tasks[day] = dict()

            if doc not in doc_tasks[day]:
                doc_tasks[day][doc] = list()

            doc_tasks[day][doc].append(task)

        for day in doc_tasks:
            for doc in doc_tasks[day]:
                yield UnaryResource(doc_tasks[day][doc])

    #
    # Only one surgery can be made in an operation room: an operation room
    # is a unary resource.
    #
    def constraint_7(self, operations):

        struct = dict()
        for (day, room, doc, surg, task) in operations:
            if day not in struct:
                struct[day] = dict()

            if room not in struct[day]:
                struct[day][room] = list()

            struct[day][room].append(task)

        for day in struct:
            for room in struct[day]:
                yield UnaryResource(struct[day][room])             

    #
    # All surgeries have to be made under the C_max, the maximum makespan value.
    #
    def constraint_8(self, operations):

        yield [task <= self.C_MAX for (_, _, _, _, task) in operations]


    #
    # The Second model is based on the Jobshop problem, but without preemption.
    #
    def model_2(self):

        operations = list()        
        for day in self.main_scruct:
            for room in self.main_scruct[day]:
                for doc in self.main_scruct[day][room]:
                    for i, (surg, var) in enumerate(self.main_scruct[day][room][doc]):
                        if var.get_value() == 1:
                            spec = self.doctors[doc]['ID_Speciality']
                            duration = int(self.specialities[spec]['Duration'])
                            task = Task(0, 720, duration)
                            operations.append((day, room, doc, surg, task))

        model = Model(
            list(self.constraint_6(operations)),
            list(self.constraint_7(operations)),
            list(self.constraint_8(operations))
        )

        #
        # Objective function: minimize the makespan value.
        #
        model.add(Minimize(self.C_MAX))

        return model, operations


def solve(param):
    ors = ORS(param)

    #
    # Step 1
    #
    model1 = ors.model_1()
    solver = model1.load('SCIP')
    solver.solve()
    ors.print_solution_step1()
    ors.print_stats()

    #
    # Step 2
    #
    model2, operations = ors.model_2()
    solver = model2.load('MiniSat')
    solver.setVerbosity(3)
    solver.setHeuristic('Scheduling', 'Promise')
    solver.solve()
    print("Is sat:", solver.is_sat())

    if solver.is_sat():
        ors.gen_scheduling_file(operations)



default = {
        'surgeries_csv' : 'surgeries.csv',
        'doctors_csv' : 'doctors.csv',
        'doctorsAvailability_csv' : 'doctorsAvailability.csv',
        'roomsAvailability_csv' : 'roomsAvailability.csv',
        'specialities_csv' : 'specialitiesDetails.csv'
}

if __name__ == '__main__':
    param = input(default)
    solve(param)
