import sys

AVAILABLE = 1
NOT_AVAILABLE = 0
VALID_INSTRUCTION_SET = ['LW', 'SW', 'L.D', 'S.D', 'DADD','DADDI','DSUB','DSUBI', 'AND', 'ANDI', 'OR', 
                        'ORI', 'LI', 'LUI', 'ADD.D', 'MUL.D', 'DIV.D', 'SUB.D', 'J', 'BEQ', 'BNE', 'HLT']
CONDITIONAL_BRANCH_INSTRUCTIONS = ['BEQ','BNE']
UNCONDITIONAL_BRANCH_INSTRUCTIONS = ['J']
THREE_OPERAND_INSTRUCTIONS = ['DADD','DADDI','DSUB','DSUBI','ADD.D', 'MUL.D', 'DIV.D', 'SUB.D', 'AND','ANDI','OR','ORI']
LOAD_INSTRUCTIONS = ['LW', 'L.D', 'LI', 'LUI']
STORE_INSTRUCTIONS = ['SW', 'S.D']
STRING_OPERTOR_MAP = {'DADD':'+','DADDI':'+', 'DSUB':'-','DSUBI':'-', 'ADD.D':'+', 'SUB.D':'-', 'MUL.D':'*','DIV.D':'/',
                        'AND':'&','ANDI':'&','OR':'|','ORI':'|'}
FUNCTIONAL_UNITS = ['INTEGER','DATA TRANSFER', 'CONTROL','SPECIAL PURPOSE','FP ADDER','FP MULTIPLIER','FP DIVIDER','I-CACHE']
INSTRUCTION_UNIT_MAP = {'LW': {'unit':'DATA TRANSFER', 'num_cycles':1},'SW': {'unit':'DATA TRANSFER', 'num_cycles':1},
                        'L.D': {'unit':'DATA TRANSFER', 'num_cycles':2},'S.D':{'unit':'DATA TRANSFER', 'num_cycles':2},
                        'HLT':{'unit':'SPECIAL PURPOSE', 'num_cycles':0},'J':{'unit':'CONTROL', 'num_cycles':0}, 
                        'BEQ':{'unit':'CONTROL', 'num_cycles':0},'BNE':{'unit':'CONTROL', 'num_cycles':0}, 
                        'DADD':{'unit':'INTEGER', 'num_cycles':1},'DADDI':{'unit':'INTEGER', 'num_cycles':1},
                        'DSUB':{'unit':'INTEGER', 'num_cycles':1},'DSUBI':{'unit':'INTEGER', 'num_cycles':1},
                        'AND':{'unit':'INTEGER', 'num_cycles':1},'ANDI':{'unit':'INTEGER', 'num_cycles':1},
                        'OR':{'unit':'INTEGER', 'num_cycles':1},'ORI':{'unit':'INTEGER', 'num_cycles':1},
                        'LI':{'unit':'INTEGER', 'num_cycles':1},'LUI':{'unit':'INTEGER', 'num_cycles':1},
                        'ADD.D':{'unit':'FP ADDER', 'num_cycles':0},'SUB.D':{'unit':'FP ADDER', 'num_cycles':0},
                        'MUL.D':{'unit':'FP MULTIPLIER', 'num_cycles':0},'DIV.D':{'unit':'FP DIVIDER', 'num_cycles':0}}
INT_REGISTERS = [0] * 32
MEMORY_LOCATIONS = [0] * 32

def decode_instruction(ins):
    label, ins_str, des, op1, op2, jump_label = None, None, None, None, None, None
    if ':' in ins[0]:
        label = ins[0].split(':')[0]
        ins = ins[1:len(ins)]
    ins_str = ins[0].upper()
    if not ins_str in VALID_INSTRUCTION_SET:
        print "INVALID INSTRUCTION:%s. Please pass only valid Instructions." %(ins_str)
        sys.exit()
    if ins_str in CONDITIONAL_BRANCH_INSTRUCTIONS:
        op1, op2, jump_label = ins[1], ins[2], ins[3]
    elif ins_str in UNCONDITIONAL_BRANCH_INSTRUCTIONS:
        jump_label = ins[1]
    elif ins_str in THREE_OPERAND_INSTRUCTIONS:
        des, op1, op2 = ins[1].split(',')[0], ins[2].split(',')[0], ins[3]
    elif ins_str in LOAD_INSTRUCTIONS:
        des, op1 = ins[1].split(',')[0], ins[2]
        #Here some processing will need if indirect addressing is used
    elif ins_str in STORE_INSTRUCTIONS:
        des, op1 = ins[2], ins[1].split(',')[0]
        #Here some processing will need if indirect addressing is used
    return label, ins_str, des, op1, op2, jump_label

def read_instructions(f1):
    ins_seq = []
    ins_dict = {}
    cnt = 0
    for line in f1:
        ins = line.split()
        label, ins_str, des, op1, op2, jump_label = decode_instruction(ins)
        ins_dict.update({cnt:{'label': label,'ins_str': ins_str,'des': des,
                    'op1':op1, 'op2':op2, 'jump_label':jump_label, 'state': -1,
                    'complete_ins':line.split('\n')[0], 
                    'functional_unit': INSTRUCTION_UNIT_MAP.get(ins_str).get('unit'),
                    'f_unit_index':-1, 'exp':None, 'temp_result': -1, 'incomplete_index':-1}})
        cnt += 1
        ins_seq.append(line.split('\n')[0])
    return ins_dict, ins_seq

def init_scoreboard(ins_dict, ins_seq, row_index_units):
    scoreboard = [[-1]*8 for _ in range(len(ins_seq))]
    for r in range(len(ins_seq)):
        scoreboard[r][5] = 'N'
        scoreboard[r][6] = 'N'
        scoreboard[r][7] = 'N'
    #print "Scoreboard:%s" %scoreboard
    functional_unit_status = [['Y']*9 for _ in range(len(row_index_units))]
    for r in range(len(row_index_units)):
        functional_unit_status[r][0] = 'N'
    #print "Functional Unit Status:%s" %functional_unit_status
    int_register_result_status = [None] * 32
    #print "Int Register Status:%s" %int_register_result_status
    float_register_result_status = [None] * 32
    #print "Float Register Status:%s" %float_register_result_status
    return scoreboard, functional_unit_status, int_register_result_status, float_register_result_status

def read_config(f2):
    units = {}
    row_index_units = [] 
    for line in f2:
        unit_name = line.split(':')[0].upper()
        if unit_name not in FUNCTIONAL_UNITS:
            print "INVALID FUNCTIONAL UNIT NAME:%s. Please pass valid names." %(unit_name)
            sys.exit()
        num_units = line.split(': ')[1].split(',')[0]
        num_cycles = int(line.split(': ')[1].split(',')[1].split()[0])
        if unit_name != 'I-CACHE':
            units.update({unit_name:int(num_units)})
        if unit_name == 'FP ADDER':
            INSTRUCTION_UNIT_MAP['ADD.D']['num_cycles'] = num_cycles
            INSTRUCTION_UNIT_MAP['SUB.D']['num_cycles'] = num_cycles
        elif unit_name == 'FP MULTIPLIER':
            INSTRUCTION_UNIT_MAP['MUL.D']['num_cycles'] = num_cycles
        elif unit_name == 'FP DIVIDER':
            INSTRUCTION_UNIT_MAP['DIV.D']['num_cycles'] = num_cycles
    units.update({'INTEGER':1,'DATA TRANSFER': 1,'CONTROL':1,'SPECIAL PURPOSE':1})
    for key, val in units.iteritems():
        for cnt in range(val):
            row_index_units.append(key)
    #print row_index_units
    #print "INSTRUCTION_UNIT_MAP:%s" %INSTRUCTION_UNIT_MAP
    return units, row_index_units

def read_data(f3):
    index = 0
    for line in f3:
        MEMORY_LOCATIONS[index] = int(line, 2)
        index += 1

def display_ins_dict(ins_dict):
    for key, val in ins_dict.iteritems():
        print "%s:%s" %(key,val)

def check_functional_unit_status(unit, row_index_units, f_unit_status):
    unit_index_list = []
    for index,u in enumerate(row_index_units):
        if u == unit:
            unit_index_list.append(index)
    for unit_index in unit_index_list:
        if f_unit_status[unit_index][0] == 'N':
            return unit_index
    return -1

def find_index_of_current_instruction(ins_seq, instruction):
    return ins_seq.index(instruction)

def check_for_WAW_hazrd(destination_reg, int_reg_res_status, float_reg_res_status):
    #print destination_reg
    if destination_reg[0] == 'R':
        if int_reg_res_status[int(destination_reg[1:len(destination_reg)]) - 1]:
            return True
    elif destination_reg[0] == 'F':
        if float_reg_res_status[int(destination_reg[1:len(destination_reg)]) - 1]:
            return True
    return False

def update_functional_unit(unit_index, f_unit_status, instruction, num_rows):
    f_unit_status[unit_index][0] = 'Y'
    f_unit_status[unit_index][1] = instruction['ins_str']
    f_unit_status[unit_index][2] = instruction['des']
    f_unit_status[unit_index][3] = instruction['op1']
    f_unit_status[unit_index][4] = instruction['op2']
    f_unit_status[unit_index][5] = None
    f_unit_status[unit_index][6] = None
    if instruction['op1']:
        for r in range(num_rows):
            if r != unit_index and instruction['op1'] == f_unit_status[r][2]:
                f_unit_status[unit_index][7] = 'N'
                break
    if instruction['op2']:
        for r in range(num_rows):
            if r != unit_index and instruction['op2'] == f_unit_status[r][2]:
                f_unit_status[unit_index][8] = 'N'
                break

def check_RAW_hazard(instruction, f_unit_status):
    unit_index = instruction['f_unit_index']
    if f_unit_status[unit_index][7] == 'Y' and f_unit_status[unit_index][8] == 'Y':
        return False
    return True

def update_output_registers(destination_reg, i_reg_res_status, f_reg_res_status):
    #print destination_reg
    if destination_reg[0] == 'R':
        i_reg_res_status[int(destination_reg[1:len(destination_reg)]) - 1] =  destination_reg
    elif destination_reg[0] == 'F':
        f_reg_res_status[int(destination_reg[1:len(destination_reg)]) - 1] = destination_reg

def read_register(register):
    if register[0] == 'R':
        val = INT_REGISTERS[int(register[1:len(register)]) - 1]
    elif register[0] == 'F':
        val = 0
    return val

def extract_values(instruction):
    op1_val, op2_val = None, None
    if instruction['ins_str'] in ['DADD','DSUB', 'AND', 'OR']:
        op1_val = read_register(instruction['op1'])
        op2_val = read_register(instruction['op2'])
    elif instruction['ins_str'] in ['DADDI','DSUBI', 'ANDI', 'ORI']: 
        op1_val = read_register(instruction['op1'])
        op2_val = int(instruction['op2'])
    return op1_val, op2_val

def load_register(instruction):
    val = None
    if instruction['ins_str'] == 'LW':
        base_register = instruction['op1'].split('(')[1].split(')')[0]
        val = read_register(base_register) - 256
    elif instruction['ins_str'] == ['LI','LUI']:
        val = int(instruction['op1'])
    return val

def store_register(instruction):
    val = None
    if instruction['ins_str'] == 'SW': 
        val1 = read_register(instruction['op1'])
        val2 = read_register(instruction['des'].split('(')[1].split(')')[0])
        val = "%s##%s" %(val1, val2)
    return val

def make_expression(v1, v2, instruction):
    operation = STRING_OPERTOR_MAP.get(instruction['ins_str'])
    return "%s%s%s" %(v1, operation, v2)

def read_operands_and_make_expression(instruction):
    exp = None
    if instruction['ins_str'] in THREE_OPERAND_INSTRUCTIONS:
        v1, v2 = extract_values(instruction)
        if v1 and v2:
            exp = make_expression(v1, v2, instruction)
    elif instruction['ins_str'] in LOAD_INSTRUCTIONS:
        exp = load_register(instruction)
    elif instruction['ins_str'] in STORE_INSTRUCTIONS:
        exp = store_register(instruction)
    return exp

def execute_instruction(instruction):
    result = None
    if instruction['ins_str'] in THREE_OPERAND_INSTRUCTIONS:
        if instruction['exp']:
            result = eval(instruction['exp'])
    elif instruction['ins_str'] in LOAD_INSTRUCTIONS:
        res = instruction['exp']
        if instruction['ins_str'] == 'LW':
            displacement = int(instruction['op1'].split('(')[0])
            base_value = res
            if (displacement + base_value) > 31:
                print "Accessing Out of Memory Data.."
                sys.exit(0)
            result = MEMORY_LOCATIONS[displacement + base_value]
        elif instruction['ins_str'] == 'LI' and res:
            result = int(res)
        elif instruction['ins_str'] == 'LUI' and res:
            result = int(res)
            result = result << 16
    elif instruction['ins_str'] in STORE_INSTRUCTIONS:
        result = instruction['exp']
        if instruction['ins_str'] == 'SW':
            source_val = int(result.split('##')[0])
            des_val = int(result.split('##')[1])
            displacement = int(instruction['des'].split('(')[0])
            if (displacement + base_value) > 31:
                print "Accessing Out of Memory Data.."
                sys.exit(0)
            MEMORY_LOCATIONS[des_val + displacement] = source_val
    return result

def write_result(instruction):
    if instruction['temp_result']:
        reg = instruction['des']
        if reg[0] == 'R':
            INT_REGISTERS[int(reg[1:len(reg)]) - 1] = instruction['temp_result']
        
def clear_functional_unit(instruction, f_unit_status, num_rows):
    unit_index = instruction['f_unit_index']
    #check the output register and mark
    output_reg = f_unit_status[unit_index][2]
    for r in range(num_rows):
        if r != unit_index and output_reg == f_unit_status[r][3]:
            f_unit_status[r][7] = 'Y'
        if r != unit_index and output_reg == f_unit_status[r][4]:
            f_unit_status[r][8] = 'Y'
    f_unit_status[unit_index][0] = 'N'
    for n in range(1,9):
        f_unit_status[unit_index][n] = 'Y'

def clear_output_registers(instruction, int_register_result_status, float_register_result_status):
    des = instruction['des']
    if des[0] == 'R':
        int_register_result_status[int(des[1:len(des)]) - 1] = None
    elif des[0] == 'F':
        float_register_result_status[int(des[1:len(des)]) - 1] = None

def generate_scoreboard(scoreboard, f_unit_status, i_reg_res_status, f_reg_res_status, ins_dict, ins_seq, row_index_units): 
    clock_counter = 2
    incomplete_ins = [ins_dict.get(0)]
    incomplete_ins[0]['state'] = 0
    scoreboard[0][0] = 1
    write_ins = []
    
    while(True):
        n = len(incomplete_ins)
        for main_index in range(n):
            instruction = incomplete_ins[main_index]
            instruction_index = find_index_of_current_instruction(ins_seq, instruction['complete_ins'])
            if instruction['state'] == 0:
                #can it be issed : check for structural hazard and WAW hazard
                unit_index = check_functional_unit_status(instruction['functional_unit'], row_index_units, f_unit_status)
                if unit_index == -1:
                    scoreboard[instruction_index][7] = 'Y' 
                WAW_status = check_for_WAW_hazrd(instruction['des'], i_reg_res_status, f_reg_res_status)
                if WAW_status:
                    scoreboard[instruction_index][6] = 'Y' 
                if WAW_status is False and unit_index != -1:
                    #Issue the instruction
                    instruction['state'] = 1
                    instruction['f_unit_index'] = unit_index
                    scoreboard[instruction_index][1] = clock_counter
                    update_output_registers(instruction['des'], i_reg_res_status, f_reg_res_status)
                    update_functional_unit(unit_index, f_unit_status, instruction, len(row_index_units)) 
                    if ins_dict.get(instruction_index+1):
                        incomplete_ins.append(ins_dict.get(instruction_index+1))
                        incomplete_ins[-1]['state'] = 0
                        scoreboard[instruction_index+1][0] = clock_counter
            elif instruction['state'] == 1:
                is_hazard = check_RAW_hazard(instruction, f_unit_status)
                if is_hazard is False:
                    instruction['state'] = 2
                    scoreboard[instruction_index][2] = clock_counter
                    exp = read_operands_and_make_expression(instruction)
                    instruction['exp'] = exp
                else:
                    scoreboard[instruction_index][5] = 'Y'
            elif instruction['state'] == 2:
                #Now check if at this current clock counter execution is finished or not
                if clock_counter - scoreboard[instruction_index][2] == INSTRUCTION_UNIT_MAP.get(instruction['ins_str']).get('num_cycles'):
                    instruction['state'] = 3
                    scoreboard[instruction_index][3] = clock_counter
                    temp_result = execute_instruction(instruction)
                    instruction['temp_result'] = temp_result
            elif instruction['state'] == 3:
                instruction['incomplete_index'] = main_index
                write_ins.append(instruction)
        
        for instruction in write_ins: 
            instruction_index = find_index_of_current_instruction(ins_seq, instruction['complete_ins'])
            scoreboard[instruction_index][4] = clock_counter
            write_result(instruction)
            clear_functional_unit(instruction, f_unit_status, len(row_index_units))
            clear_output_registers(instruction, i_reg_res_status, f_reg_res_status)
            instruction['state'] = 4
            instruction['f_unit_index'] = -1
            instruction['exp'] = None
            instruction['temp_result'] = None
            incomplete_ins.pop(instruction['incomplete_index'])
            instruction['incomplete_index'] = -1
        write_ins = []
        clock_counter += 1
        if clock_counter == 76:
            break
    for i in range(len(ins_seq)):
        print scoreboard[i]
    print MEMORY_LOCATIONS

if __name__ == '__main__':
    inst_file = sys.argv[1]
    config_file = sys.argv[2]
    data_file = sys.argv[3]
    f1 = open(inst_file, "rb")
    f2 = open(config_file, "rb")
    f3 = open(data_file, "rb")
    ins_dict, ins_seq = read_instructions(f1)
    #print "Instructions:%s" %ins_dict
    #print "Instruction Seq:%s" %ins_seq
    units, row_index_units = read_config(f2)
    #print "Units are:%s" %units
    #print "Row Index Units:%s" %row_index_units
    read_data(f3)
    scoreboard, f_unit_status, i_reg_res_status, f_reg_res_status = init_scoreboard(ins_dict, ins_seq, row_index_units)
    generate_scoreboard(scoreboard, f_unit_status, i_reg_res_status, f_reg_res_status, ins_dict, ins_seq, row_index_units)
    f1.close()
    f2.close()
    f3.close()
