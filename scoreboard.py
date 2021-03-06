#!/usr/bin/env python
import sys
from copy import deepcopy

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
DATA_MEM = {}
SET0_CACHE = {'latest_block_index':0, 'blocks': [{},{}]}
SET1_CACHE ={'latest_block_index':0, 'blocks': [{},{}]}
I_CACHE_BLOCK_SIZE = 0
I_CACHE_WORD_SIZE = 0
I_CACHE = []

def decode_instruction(ins):
    label, ins_str, des, op1, op2, jump_label, displacement = None, None, None, None, None, None, None
    if ':' in ins[0]:
        label = ins[0].split(':')[0]
        ins = ins[1:len(ins)]
    elif ':' in ins[1]:
        label = ins[0]
        ins = ins[2:len(ins)]
    ins_str = ins[0].upper()
    if not ins_str in VALID_INSTRUCTION_SET:
        print "INVALID INSTRUCTION:%s. Please pass only valid Instructions." %(ins_str)
        sys.exit()
    if ins_str in CONDITIONAL_BRANCH_INSTRUCTIONS:
        op1, op2, jump_label = ins[1].split(',')[0], ins[2].split(',')[0], ins[3]
    elif ins_str in UNCONDITIONAL_BRANCH_INSTRUCTIONS:
        jump_label = ins[1]
    elif ins_str in THREE_OPERAND_INSTRUCTIONS:
        des, op1, op2 = ins[1].split(',')[0], ins[2].split(',')[0], ins[3]
    elif ins_str in LOAD_INSTRUCTIONS:
        if ins_str in ['LI', 'LUI']:
            des, op1 = ins[1].split(',')[0], ins[2]
        elif ins_str in ['LW','L.D']:
            des = ins[1].split(',')[0]
            op1 = ins[2].split('(')[1].split(')')[0]
            displacement = int(ins[2].split('(')[0])
    elif ins_str in STORE_INSTRUCTIONS:
        op1 = ins[1].split(',')[0]
        des = ins[2].split('(')[1].split(')')[0]
        displacement = int(ins[2].split('(')[0])
    return label, ins_str, des, op1, op2, jump_label, displacement

def read_instructions(f1):
    ins_seq = []
    ins_dict = {}
    cnt = 0
    for line in f1:
        #print line
        ins = line.split()
        #print ins
        if 'HLT' in ins:
            label, ins_str, des, op1, op2, jump_label, displacement = None, 'HLT', None, None, None, None, None
        else:
            label, ins_str, des, op1, op2, jump_label, displacement = decode_instruction(ins)
        ins_dict.update({cnt:{'label': label,'ins_str': ins_str,'des': des,
                    'displacement': displacement,
                    'op1':op1, 'op2':op2, 'jump_label':jump_label, 'state': -1,
                    'complete_ins':line.split('\n')[0],'stall_lock':False, 
                    'functional_unit': INSTRUCTION_UNIT_MAP.get(ins_str).get('unit'),
                    'f_unit_index':-1, 'exp':None, 'temp_result': -1, 'incomplete_index':-1,
                    'output_count':0, 'clocks':[-1,-1,-1,-1,-1,'N','N','N'],
                    'branch_next_ins': False, 'd_cache_miss_penalty':0}})
        cnt += 1
        ins_seq.append(line.split('\n')[0])
    return ins_dict, ins_seq

def init_scoreboard(ins_dict, ins_seq, row_index_units):
    global I_CACHE_WORD_SIZE
    global I_CACHE_BLOCK_SIZE
    global I_CACHE
    global SET0_CACHE
    global SET1_CACHE

    scoreboard = [[-1]*8 for _ in range(len(ins_seq))]
    for r in range(len(ins_seq)):
        scoreboard[r][5] = 'N'
        scoreboard[r][6] = 'N'
        scoreboard[r][7] = 'N'
    functional_unit_status = [['Y']*9 for _ in range(len(row_index_units))]
    for r in range(len(row_index_units)):
        functional_unit_status[r][0] = 'N'
    int_register_result_status = [None] * 32
    float_register_result_status = [None] * 32
    I_CACHE = [[-1]*I_CACHE_WORD_SIZE for _ in range(I_CACHE_BLOCK_SIZE)]
    for x in SET0_CACHE.get('blocks'):
        x.update({'addresses':[], 'values':{}})
    for x in SET1_CACHE.get('blocks'):
        x.update({'addresses':[], 'values':{}})
    return scoreboard, functional_unit_status, int_register_result_status, float_register_result_status

def read_config(f2):
    global I_CACHE_BLOCK_SIZE
    global I_CACHE_WORD_SIZE
    units = {}
    row_index_units = [] 
    for line in f2:
        unit_name = line.split(':')[0].upper()
        if unit_name not in FUNCTIONAL_UNITS:
            print "INVALID FUNCTIONAL UNIT NAME:%s. Please pass valid names." %(unit_name)
            sys.exit()
        num_units = line.split(': ')[1].split(',')[0]
        num_cycles = int(line.split(': ')[1].split(',')[1].split()[0])
        if unit_name == 'I-CACHE':
            I_CACHE_BLOCK_SIZE = int(num_units)
            I_CACHE_WORD_SIZE = int(num_cycles)
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
    return units, row_index_units

def read_data(f3):
    global MEMORY_LOCATIONS
    global DATA_MEM
    index = 0
    memory_initial_address = 256
    for line in f3:
        DATA_MEM.update({memory_initial_address: int(line,2)})
        memory_initial_address += 4
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
    if destination_reg and destination_reg[0] == 'R':
        if int_reg_res_status[int(destination_reg[1:len(destination_reg)]) - 1]:
            return True
    elif destination_reg and destination_reg[0] == 'F':
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
    if destination_reg and destination_reg[0] == 'R':
        i_reg_res_status[int(destination_reg[1:len(destination_reg)]) - 1] =  destination_reg
    elif destination_reg and destination_reg[0] == 'F':
        f_reg_res_status[int(destination_reg[1:len(destination_reg)]) - 1] = destination_reg

def read_register(register):
    global INT_REGISTERS
    if register[0] == 'R':
        val = INT_REGISTERS[int(register[1:len(register)]) - 1]
    elif register[0] == 'F':
        val = 0
    #print "Register is:%s and val is;%s" %(register, val)
    return val

def extract_values(instruction):
    op1_val, op2_val = None, None
    if instruction['ins_str'] in ['DADD','DSUB', 'AND', 'OR']:
        op1_val = read_register(instruction['op1'])
        op2_val = read_register(instruction['op2'])
    elif instruction['ins_str'] in ['DADDI','DSUBI', 'ANDI', 'ORI']: 
        op1_val = read_register(instruction['op1'])
        op2_val = int(instruction['op2'])
    elif instruction['ins_str'] in ['ADD.D', 'MUL.D','SUB.D','DIV.D']:
        op1_val = 0
        op2_val = 0
    return op1_val, op2_val

def load_register(instruction):
    val = None
    if instruction['ins_str'] in ['LW','L.D']:
        base_register = instruction['op1']
        #print "Base Register:%s" %base_register
        #val = read_register(base_register) - 256
        val = read_register(base_register)
        #print "Value is:%s" %val
    elif instruction['ins_str'] in ['LI','LUI']:
        #print 'Instruction is;%s and value is%s' %(instruction['complete_ins'], instruction['op1'])
        val = int(instruction['op1'])
    return val

def store_register(instruction):
    val = None
    if instruction['ins_str'] == 'SW': 
        val1 = read_register(instruction['op1'])
        val2 = read_register(instruction['des'])
        val = "%s##%s" %(val1, val2)
    elif instruction['ins_str'] == 'S.D':
        val2 = read_register(instruction['des'])
        val1 = "0"
        val = "%s##%s" %(val1, val2)
    return val

def make_expression(v1, v2, instruction):
    operation = STRING_OPERTOR_MAP.get(instruction['ins_str'])
    return "%s%s%s" %(v1, operation, v2)

def execute_conditional_branch(instruction):
    op1_val = read_register(instruction['op1'])
    op2_val = read_register(instruction['op2'])
    if instruction['ins_str'] == 'BNE':
        if op1_val != op2_val:
            return True
    elif instruction['ins_str'] == 'BEQ':
        if op1_val == op2_val:
            return True
    return False
    
def read_operands_and_make_expression(instruction):
    exp = None
    if instruction['ins_str'] in THREE_OPERAND_INSTRUCTIONS:
        v1, v2 = extract_values(instruction)
        if v1 and v2:
            exp = make_expression(v1, v2, instruction)
    elif instruction['ins_str'] in LOAD_INSTRUCTIONS:
        exp = load_register(instruction)
        #print "Instruction is:%s and exp is;%s" %(instruction['complete_ins'], exp)
    elif instruction['ins_str'] in STORE_INSTRUCTIONS:
        exp = store_register(instruction)
    elif instruction['ins_str'] in CONDITIONAL_BRANCH_INSTRUCTIONS:
        exp = execute_conditional_branch(instruction)
    elif instruction['ins_str'] in UNCONDITIONAL_BRANCH_INSTRUCTIONS:
        exp = execute_unconditional_branch(instruction)
    return exp

def execute_instruction(instruction):
    global MEMORY_LOCATIONS
    global DATA_MEM
    #print MEMORY_LOCATIONS
    result, address = None, None
    if instruction['ins_str'] in THREE_OPERAND_INSTRUCTIONS:
        if instruction['exp']:
            result = eval(instruction['exp'])
    elif instruction['ins_str'] in LOAD_INSTRUCTIONS:
        res = instruction['exp']
        #print "Instruction is:%s and result is;%s" %(instruction['complete_ins'], res)
        if instruction['ins_str'] in ['LW','L.D']:
            displacement = instruction['displacement']
            base_value = res
            if (displacement + base_value) > 380:
                print "Accessing Out of Memory Data.."
                sys.exit(0)
            address = displacement + base_value
            result = DATA_MEM[displacement + base_value]
        elif instruction['ins_str'] == 'LI':
            if res is not None:
                result = int(res)
                #print "Instruction is:%s and result in LI block is:%s" %(instruction['complete_ins'], res)
        elif instruction['ins_str'] == 'LUI':
            if res is not None:
                result = int(res)
                result = result << 16
    elif instruction['ins_str'] in STORE_INSTRUCTIONS:
        result = instruction['exp']
        if instruction['ins_str'] in ['SW', 'S.D']:
            #print "Result in Destination SW is;%s" %(result)
            source_val = int(result.split('##')[0])
            des_val = int(result.split('##')[1]) 
            displacement = instruction['displacement']
            if (displacement + des_val) > 380:
                print "Accessing Out of Memory Data.."
                sys.exit(0)
            address = displacement + des_val
            #MEMORY_LOCATIONS[des_val + displacement] = source_val
            DATA_MEM[des_val + displacement] = source_val
    elif instruction['ins_str'] in CONDITIONAL_BRANCH_INSTRUCTIONS:
        pass
    return result, address

def write_result(instruction):
    #print "Instruction is:%s and result in write is:%s" %(instruction['complete_ins'], instruction['temp_result'])
    global INT_REGISTERS
    reg = instruction['des']
    #print "Instruction is %s and destination is %s" %(instruction['complete_ins'], reg)
    if reg[0] == 'R' and instruction['temp_result'] is not None:
        INT_REGISTERS[int(reg[1:len(reg)]) - 1] = instruction['temp_result']
        
def clear_functional_unit(instruction, f_unit_status, num_rows):
    unit_index = instruction['f_unit_index']
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
    if des and des[0] == 'R':
        int_register_result_status[int(des[1:len(des)]) - 1] = None
    elif des and des[0] == 'F':
        float_register_result_status[int(des[1:len(des)]) - 1] = None

def handle_branch_result(instruction, instruction_index, output_list, exp, ins_dict, fetch_count):
    is_branch_taken = False
    loop_start_ins = None
    if exp:
        #print "Branch Satisfied..."
        f_k = None
        jump_label = instruction['jump_label']
        #print jump_label
        #print ins_dict
        for key,val in ins_dict.iteritems():
            if val.get('label') == jump_label:
                f_k = key
                break
        loop_start_ins = deepcopy(ins_dict.get(f_k))
        loop_start_ins.update({'stall_lock':False, 'f_unit_index':-1, 'exp': None, 'temp_result': -1, 
            'incomplete_ins': -1, 'output_count': fetch_count, 'state':-1, 'clocks':[-1,-1,-1,-1,-1,'N','N','N']})  
        #output_list.append(deepcopy(ins_dict.get(instruction_index+1)))
        is_branch_taken = True
    else:
        #print "Seq Count:%s" %(instruction_index)
        #print "Instruction Dict:%s" %(ins_dict)
        ins = ins_dict.get(instruction_index+1)
        if ins:
            ins['stall_lock'] = False
    return (is_branch_taken, loop_start_ins)

def populate_instruction_cache(instruction_index):
    global I_CACHE
    global I_CACHE_BLOCK_SIZE
    global I_CACHE_WORD_SIZE
    
    block_no = (instruction_index / I_CACHE_WORD_SIZE) % I_CACHE_BLOCK_SIZE
    start_word_address = instruction_index - (instruction_index % I_CACHE_WORD_SIZE)
    for i in range(I_CACHE_WORD_SIZE):
        I_CACHE[block_no][i] = start_word_address
        start_word_address += 1

def check_instruction_cache(instruction_index):
    global I_CACHE
    global I_CACHE_BLOCK_SIZE
    global I_CACHE_WORD_SIZE
    
    block_no = (instruction_index / I_CACHE_WORD_SIZE) % I_CACHE_BLOCK_SIZE
    offset = instruction_index % I_CACHE_WORD_SIZE

    if I_CACHE[block_no][offset] == instruction_index:
        return False
    else:
        return True

def calculate_set_no(address):
    return (((address / 4) / 4) % 2)

def insert_into_data_cache(address):
    global SET0_CACHE
    global SET1_CACHE
    global DATA_MEM

    oldest_block = 0
    is_empty_block_found = False
    set_no = calculate_set_no(address)
    start_word_address = address - (address % 16)
    if set_no == 0:
        for index, block in enumerate(SET0_CACHE.get('blocks')):
            if not block.get('addresses'):
                is_empty_block_found = True
                for b in range(4):
                    block['addresses'].append(start_word_address)
                    block['values'].update({start_word_address:DATA_MEM.get(start_word_address)})
                    start_word_address += 4
                SET0_CACHE['latest_block_index'] = index
                break
        if not is_empty_block_found:
            if SET0_CACHE['latest_block_index'] == 0:
                oldest_block = 1
            else:
                oldest_block = 0
            #Now Replace oldest block
            SET0_CACHE['blocks'][oldest_block]['addresses'] = []
            SET0_CACHE['blocks'][oldest_block]['values'] = {}
            for b in range(4):
                SET0_CACHE['blocks'][oldest_block]['addresses'].append(start_word_address)
                SET0_CACHE['blocks'][oldest_block]['values'].update({start_word_address:DATA_MEM.get(start_word_address)})
                start_word_address += 4
            SET0_CACHE['latest_block_index'] = oldest_block
    elif set_no == 1: 
        for index, block in enumerate(SET1_CACHE.get('blocks')):
            if not block.get('addresses'):
                is_empty_block_found = True
                for b in range(4):
                    block['addresses'].append(start_word_address)
                    block['values'].update({start_word_address:DATA_MEM.get(start_word_address)})
                    start_word_address += 4
                SET1_CACHE['latest_block_index'] = index
                break
        if not is_empty_block_found:
            if SET1_CACHE['latest_block_index'] == 0:
                oldest_block = 1
            else:
                oldest_block = 0
            #Now Replace oldest block
            SET1_CACHE['blocks'][oldest_block]['addresses'] = []
            SET1_CACHE['blocks'][oldest_block]['values'] = {}
            for b in range(4):
                SET1_CACHE['blocks'][oldest_block]['addresses'].append(start_word_address)
                SET1_CACHE['blocks'][oldest_block]['values'].update({start_word_address:DATA_MEM.get(start_word_address)})
                start_word_address += 4
            SET1_CACHE['latest_block_index'] = oldest_block

def search_in_data_cache(address):
    global SET0_CACHE
    global SET1_CACHE
    global DATA_MEM
    is_found = True
    set_no = calculate_set_no(address)
    if set_no == 0: 
        for index, block in enumerate(SET0_CACHE.get('blocks')):
            if address in block['addresses']:
                #Cache hit - No Penalty
                SET0_CACHE['latest_block_index'] = index
                return is_found

        #Following call may be shifted in giant loop for proper cycle counting
        #insert_into_data_cache(address)     
    elif set_no == 1: 
        for index, block in enumerate(SET1_CACHE.get('blocks')):
            if address in block['addresses']:
                #Cache hit - No Penalty
                SET1_CACHE['latest_block_index'] = index
                return is_found

        #Following call may be shifted in giant loop for proper cycle counting
        #insert_into_data_cache(address)
    return False

def generate_scoreboard(f_unit_status, i_reg_res_status, f_reg_res_status, ins_dict, ins_seq, row_index_units, f4): 
    i_cache_miss_penalty = 3 * I_CACHE_WORD_SIZE
    populate_instruction_cache(0)
    clock_counter = 3 * I_CACHE_WORD_SIZE + 1
    incomplete_ins = [ins_dict.get(0)]
    incomplete_ins[0]['state'] = -1
    incomplete_ins[0]['output_count'] = 0
    incomplete_ins[0]['clocks'][0] = i_cache_miss_penalty + 1
    write_ins = []
    output_list  = []
    fetch_count = 1
    penlety_lock = -1000
    is_system_bus_available = False
    bus_acquisition_counter = -1
    bus_release_time = -1
    pending_bus_req = False
    terminate_scoreboard = False
    previous_ins = None
    i_cache_miss_count = 1
    i_cache_access_count = 0
    d_cache_access_count = 0
    d_cache_miss_count = 0

    while(True):
        n = len(incomplete_ins)
        main_index = 0
        if len(incomplete_ins) == 2:
            if incomplete_ins[0]['ins_str'] == 'HLT' and incomplete_ins[1]['ins_str'] == 'HLT':
                if incomplete_ins[0]['clocks'][1] != -1 and incomplete_ins[1]['clocks'][0] != -1:
                    output_list.append(incomplete_ins[0])
                    output_list.append(incomplete_ins[1])
                    break
        if clock_counter == 128:
            print "Incomplete list:%s" %(incomplete_ins)
        while main_index < n:
            instruction = incomplete_ins[main_index]
            instruction_index = find_index_of_current_instruction(ins_seq, instruction['complete_ins'])
            if instruction['state'] == 0 and instruction['stall_lock'] is False:
                unit_index = check_functional_unit_status(instruction['functional_unit'], row_index_units, f_unit_status)
                if unit_index == -1:
                    instruction['clocks'][7] = 'Y'
                WAW_status = check_for_WAW_hazrd(instruction['des'], i_reg_res_status, f_reg_res_status)
                if WAW_status:
                    instruction['clocks'][6] = 'Y'
                if WAW_status is False and unit_index != -1:
                    instruction['state'] = 1
                    instruction['f_unit_index'] = unit_index
                    instruction['clocks'][1] = clock_counter
                    update_output_registers(instruction['des'], i_reg_res_status, f_reg_res_status)
                    update_functional_unit(unit_index, f_unit_status, instruction, len(row_index_units))
                    if ins_dict.get(instruction_index+1):
                        incomplete_ins.append(ins_dict.get(instruction_index+1))
                        incomplete_ins[-1]['state'] = -1
                        #incomplete_ins[-1]['clocks'][0] = clock_counter
                        incomplete_ins[-1]['output_count'] = fetch_count
                        prev_ins = instruction
                        n = n + 1
                        fetch_count += 1
                        if instruction['ins_str'] in ['BEQ', 'BNE', 'J']:
                            incomplete_ins[-1]['stall_lock'] = True
                    if instruction['ins_str'] == 'J':
                        branch_res = handle_branch_result(instruction, instruction_index, output_list, True, ins_dict, fetch_count)
                        incomplete_ins[-1]['stall_lock'] = False
                        if branch_res[0]:
                            #branch_res[1]['clocks'][0] = clock_counter + 1
                            incomplete_ins.append(branch_res[1])
                            incomplete_ins[main_index+1]['branch_next_ins'] = True
                            #incomplete_ins.pop(main_index+1)
                        clear_functional_unit(instruction, f_unit_status, len(row_index_units))
                        incomplete_ins.pop(main_index)
                        output_list.append(deepcopy(instruction))
                        break
            elif instruction['state'] == -1:
                if check_instruction_cache(instruction_index) and penlety_lock == -1000:
                    i_cache_miss_count += 1
                    is_system_bus_available = False
                    bus_release_time = clock_counter + i_cache_miss_penalty
                    #bus_acquisition_counter = clock_counter 
                    penlety_lock = prev_ins['clocks'][0] + i_cache_miss_penalty
                if penlety_lock < clock_counter:
                    i_cache_access_count += 1
                    if instruction['ins_str'] in ['L.D','S.D']:
                        d_cache_access_count += 2
                    elif instruction['ins_str'] in ['LW','SW']:
                        d_cache_access_count += 1 
                    is_system_bus_available = True
                    bus_acquisition_counter = -1
                    populate_instruction_cache(instruction_index)
                    instruction['state'] = 0
                    instruction['clocks'][0] = clock_counter
                    penlety_lock = -1000
                    if instruction['branch_next_ins']:
                        output_list.append(deepcopy(instruction))
                        #incomplete_ins[main_index + 1]['state'] = -1
                        instruction['branch_next_ins'] = False
                        incomplete_ins.pop(main_index)
                        main_index = main_index + 1
            elif instruction['state'] == 1 and instruction['stall_lock'] is False:
                is_hazard = check_RAW_hazard(instruction, f_unit_status)
                if is_hazard is False:
                    instruction['state'] = 2
                    instruction['clocks'][2] = clock_counter
                    exp = read_operands_and_make_expression(instruction)
                    instruction['exp'] = exp
                    if instruction['ins_str'] in CONDITIONAL_BRANCH_INSTRUCTIONS:
                        branch_res = handle_branch_result(instruction, instruction_index, output_list, exp, ins_dict, fetch_count)
                        if branch_res[0]:
                            clock_counter += 1
                            #branch_res[1]['clocks'][0] = clock_counter
                            incomplete_ins.append(branch_res[1])
                            incomplete_ins[main_index+1]['branch_next_ins'] = True
                            #incomplete_ins.pop(main_index+1)
                        clear_functional_unit(instruction, f_unit_status, len(row_index_units))
                        incomplete_ins.pop(main_index)
                        output_list.append(deepcopy(instruction))
                        break
                else:
                    instruction['clocks'][5] = 'Y' 
            elif instruction['state'] == 2 and instruction['stall_lock'] is False:
                if instruction['ins_str'] == 'DADD':
                    print "Clock Counter is:%s" %(clock_counter)
                if clock_counter - (instruction['d_cache_miss_penalty'] + instruction['clocks'][2]) == INSTRUCTION_UNIT_MAP.get(instruction['ins_str']).get('num_cycles') or pending_bus_req:
                    if instruction['ins_str'] not in ['CONDITIONAL_BRANCH_INSTRUCTIONS']:
                        temp_result, address = execute_instruction(instruction)
                        if instruction['ins_str'] in ['LW','SW'] and address:
                            if is_system_bus_available is True:
                                pending_bus_req = False
                                if search_in_data_cache(address):
                                    print "Cache Hit for instruction and address:%s %s" %(instruction['complete_ins'], address)
                                    instruction['state'] = 3
                                    instruction['temp_result'] = temp_result
                                    instruction['clocks'][3] = clock_counter
                                else:
                                    d_cache_miss_count += 1
                                    insert_into_data_cache(address)
                                    print "Cache Miss for instruction and address:%s %s" %(instruction['complete_ins'], address)
                                    instruction['d_cache_miss_penalty'] += 12
                            else:
                                pending_bus_req = True
                                if clock_counter == bus_release_time:
                                    bus_release_time = -1
                                    actual_cycle_count = clock_counter + 12 + INSTRUCTION_UNIT_MAP.get(instruction['ins_str']).get('num_cycles') -1
                                    x = actual_cycle_count - (INSTRUCTION_UNIT_MAP.get(instruction['ins_str']).get('num_cycles') + instruction['clocks'][2])
                                    instruction['d_cache_miss_penalty'] = x - 12
                        elif instruction['ins_str'] in ['L.D','S.D'] and address:
                            if is_system_bus_available is True:
                                pending_bus_req = False
                                if search_in_data_cache(address):
                                    if search_in_data_cache(address + 4):
                                        print "Cache Hit for instruction and address:%s %s" %(instruction['complete_ins'], address)
                                        instruction['state'] = 3
                                        instruction['temp_result'] = temp_result
                                        instruction['clocks'][3] = clock_counter
                                    else:
                                        d_cache_miss_count += 1
                                        insert_into_data_cache(address+4)
                                        instruction['d_cache_miss_penalty'] += 12
                                else:
                                    d_cache_miss_count += 1
                                    insert_into_data_cache(address)
                                    if search_in_data_cache(address + 4):
                                        instruction['d_cache_miss_penalty'] += 12
                                    else:
                                        d_cache_miss_count += 1
                                        #insert_into_data_cache(address)
                                        insert_into_data_cache(address + 4)
                                        instruction['d_cache_miss_penalty'] += 24
                            else:
                                pending_bus_req = True
                                if clock_counter == bus_release_time:
                                    bus_release_time = -1
                                    actual_cycle_count = clock_counter + 12 + INSTRUCTION_UNIT_MAP.get(instruction['ins_str']).get('num_cycles') -1
                                    x = actual_cycle_count - (INSTRUCTION_UNIT_MAP.get(instruction['ins_str']).get('num_cycles') + instruction['clocks'][2])
                                    instruction['d_cache_miss_penalty'] = x - 12
                                #instruction['d_cache_miss_penalty'] = 11
                        else:
                            if clock_counter - instruction['clocks'][2] == INSTRUCTION_UNIT_MAP.get(instruction['ins_str']).get('num_cycles'): 
                                instruction['state'] = 3
                                instruction['temp_result'] = temp_result
                                instruction['clocks'][3] = clock_counter
            elif instruction['state'] == 3 and instruction['stall_lock'] is False:
                instruction['incomplete_index'] = main_index
                write_ins.append(instruction)
            main_index = main_index + 1

        for instruction in write_ins: 
            instruction_index = find_index_of_current_instruction(ins_seq, instruction['complete_ins'])
            instruction['clocks'][4] = clock_counter
            if instruction['ins_str'] not in ['SW', 'S.D']:
                write_result(instruction)
            clear_functional_unit(instruction, f_unit_status, len(row_index_units))
            clear_output_registers(instruction, i_reg_res_status, f_reg_res_status)
            output_list.append(deepcopy(instruction))
            instruction['state'] = 4
            instruction['f_unit_index'] = -1
            instruction['d_cache_miss_penalty'] = 0
            instruction['exp'] = None
            instruction['temp_result'] = None
            incomplete_ins.pop(instruction['incomplete_index'])
            instruction['incomplete_index'] = -1
        write_ins = []
        clock_counter += 1
    op_list = []
    s = "%-20s %-5s %-5s %-5s %-5s %-5s %-5s %-5s %-5s\n" %('Instruction','Fetch', 'Issue','Read','Exec','Write','RAW','WAW','Struct')
    f4.write(s)
    for i in range(0,fetch_count):
        for op in output_list:
            if op and op['output_count'] == i:
                print "%s\t%s" %(op['complete_ins'], op['clocks'])
                c0, c1, c2, c3, c4, c5, c6,c7 = op['clocks'][0], op['clocks'][1], op['clocks'][2], op['clocks'][3], op['clocks'][4], op['clocks'][5], op['clocks'][6], op['clocks'][7]
                if c0 == -1:
                    c0 = ''
                if c1 == -1:
                    c1 = ''
                if c2 == -1:
                    c2 = ''
                if c3 == -1:
                    c3 = ''
                if c4 == -1:
                    c4 = ''
                op_list.append("%-20s %-5s %-5s %-5s %-5s %-5s %-5s %-5s %-5s\n" %(op['complete_ins'], c0, c1, c2, c3, c4, c5, c6, c7))

    for op in op_list:
        f4.write(op)
    print "Total Number of access requsts for instruction cahce:%s" %(i_cache_access_count)
    f4.write("\n\nTotal Number of access requsts for instruction cahce:%s" %(i_cache_access_count))
    print "Number of instruction cahce hits:%s" %(i_cache_access_count - i_cache_miss_count)
    f4.write("\n\nNumber of instruction cahce hits:%s" %(i_cache_access_count - i_cache_miss_count))
    print "Total Number of Cache requsts for Data Cache:%s" %(d_cache_access_count)
    f4.write("\n\nTotal Number of Cache requsts for Data Cache:%s" %(d_cache_access_count))
    print "Total Number of Cache Hits for Data Cache:%s" %(d_cache_access_count - d_cache_miss_count)
    f4.write("\n\nTotal Number of Cache Hits for Data Cache:%s" %(d_cache_access_count - d_cache_miss_count))


if __name__ == '__main__':
    if len(sys.argv) != 5:
        print "Usage: python inst.txt data.txt config.txt result.txt"
        sys.exit(0)
    inst_file = sys.argv[1]
    data_file = sys.argv[2]
    config_file = sys.argv[3]
    result_file = sys.argv[4]
    f1 = open(inst_file, "rb")
    f2 = open(config_file, "rb")
    f3 = open(data_file, "rb")
    f4 = open(result_file, "wb")
    ins_dict, ins_seq = read_instructions(f1)
    units, row_index_units = read_config(f2)
    read_data(f3)
    scoreboard, f_unit_status, i_reg_res_status, f_reg_res_status = init_scoreboard(ins_dict, ins_seq, row_index_units)
    generate_scoreboard(f_unit_status, i_reg_res_status, f_reg_res_status, ins_dict, ins_seq, row_index_units, f4)
    f1.close()
    f2.close()
    f3.close()
    f4.close()

