import llvmlite.ir as ir
import llvmlite.binding as llvm

from tokens import TokenType
from parser import (
    Program, Function, Print, Number, BinaryOp,
    VarDecl, Variable, Assignment, If, While,
    Return, ArrayLiteral, ArrayIndex, FloatNode,
    Call, StringNode, BoolNode, For, Import,
)


class LLVMCodeGenerator:
    def __init__(self):
        llvm.initialize_native_target()
        llvm.initialize_native_asmprinter()

        self.module = ir.Module(name="cstar_module")
        self.module.triple = llvm.get_default_triple()

        self.builder = None
        self.variables = {}
        self.classes = {}

        self.i32 = ir.IntType(32)
        self.f64 = ir.DoubleType()
        self.i8_ptr = ir.IntType(8).as_pointer()
        self.void_ty = ir.VoidType()

        printf_ty = ir.FunctionType(self.i32, [self.i8_ptr], var_arg=True)
        self.printf = ir.Function(self.module, printf_ty, name="printf")
        exp_ty = ir.FunctionType(self.f64, [self.f64])
        self.exp_func = ir.Function(self.module, exp_ty, name="exp")
        self.exp_func.attributes.add("readnone")
        self.exp_func.attributes.add("nounwind")

        csv_ty = ir.FunctionType(self.f64.as_pointer(), [self.i8_ptr, self.i32])
        self.load_csv_func = ir.Function(self.module, csv_ty, name="load_csv_native")

        self.sqrt_func = ir.Function(self.module, exp_ty, name="sqrt")
        self.sqrt_func.attributes.add("readnone")
        self.sqrt_func.attributes.add("nounwind")

        self.log_func = ir.Function(self.module, exp_ty, name="log")
        self.log_func.attributes.add("readnone")
        self.log_func.attributes.add("nounwind")

        pow_ty = ir.FunctionType(self.f64, [self.f64, self.f64])
        self.pow_func = ir.Function(self.module, pow_ty, name="pow")
        self.pow_func.attributes.add("readnone")
        self.pow_func.attributes.add("nounwind")

        free_ty = ir.FunctionType(self.void_ty, [self.i8_ptr])
        self.free_func = ir.Function(self.module, free_ty, name="free")

        malloc_ty = ir.FunctionType(self.i8_ptr, [self.i32])
        self.malloc_func = ir.Function(self.module, malloc_ty, name="malloc")

        self.i64 = ir.IntType(64)
        self.i1 = ir.IntType(1)
        memcpy_ty = ir.FunctionType(self.void_ty, [self.i8_ptr, self.i8_ptr, self.i64, self.i1])
        self.memcpy_func = ir.Function(self.module, memcpy_ty, name="llvm.memcpy.p0i8.p0i8.i64")

        strlen_ty = ir.FunctionType(self.i32, [self.i8_ptr])
        self.strlen_func = ir.Function(self.module, strlen_ty, name="strlen")
        self.strlen_func.attributes.add("readnone")
        self.strlen_func.attributes.add("nounwind")

        strcmp_ty = ir.FunctionType(self.i32, [self.i8_ptr, self.i8_ptr])
        self.strcmp_func = ir.Function(self.module, strcmp_ty, name="strcmp")
        self.strcmp_func.attributes.add("readonly")
        self.strcmp_func.attributes.add("nounwind")

        fabs_ty = ir.FunctionType(self.f64, [self.f64])
        self.fabs_func = ir.Function(self.module, fabs_ty, name="fabs")
        self.fabs_func.attributes.add("readnone")
        self.fabs_func.attributes.add("nounwind")

        round_func_ty = ir.FunctionType(self.f64, [self.f64])
        self.round_func = ir.Function(self.module, round_func_ty, name="round")
        self.round_func.attributes.add("readnone")
        self.round_func.attributes.add("nounwind")

        get_time_ty = ir.FunctionType(self.f64, [])
        self.get_time_func = ir.Function(self.module, get_time_ty, name="get_time")
        self.get_time_func.attributes.add("readnone")
        self.get_time_func.attributes.add("nounwind")

        self.csv_var_sizes = {}
        self._pending_csv_size = None
        self._fmt_cache = {}

    # =====================================================
    # CORE
    # =====================================================
    def generate(self, ast):
        self.visit(ast)
        print(self.module)

    def visit(self, node):
        if node is None:
            return None
        return getattr(self, f"visit_{type(node).__name__}", self.generic_visit)(node)

    def generic_visit(self, node):
        raise Exception(f"No visit_{type(node).__name__}")

    # =====================================================
    # PROGRAM
    # =====================================================
    def visit_Program(self, node):
        fn_type = ir.FunctionType(self.i32, [])
        main = ir.Function(self.module, fn_type, name="main")

        block = main.append_basic_block("entry")
        self.builder = ir.IRBuilder(block)

        for stmt in node.statements:
            self.visit(stmt)

        if not self.builder.block.is_terminated:
            self.builder.ret(ir.Constant(self.i32, 0))

    # =====================================================
    # LITERALS
    # =====================================================
    def visit_Number(self, node):
        return ir.Constant(self.i32, int(node.value))

    def visit_FloatNode(self, node):
        return ir.Constant(self.f64, float(node.value))

    def visit_BoolNode(self, node):
        return ir.Constant(self.i32, 1 if node.value else 0)

    def visit_StringNode(self, node):
        text = bytearray((node.value + "\0").encode())

        ty = ir.ArrayType(ir.IntType(8), len(text))
        name = f"str_{len(self.module.globals)}"

        glob = ir.GlobalVariable(self.module, ty, name=name)
        glob.global_constant = True
        glob.initializer = ir.Constant(ty, text)

        return self.builder.gep(glob, [self.i32(0), self.i32(0)])

    # ============
    # VARIABLES 
    # =========
    def visit_VarDecl(self, node):
        val = self.visit(node.value)
        if self._pending_csv_size is not None:
            self.csv_var_sizes[node.name] = ir.Constant(self.i32, self._pending_csv_size)
            self._pending_csv_size = None
        if node.type_annotation == "float" and val.type == self.i32:
            val = self.builder.sitofp(val, self.f64)
            ptr = self.builder.alloca(self.f64, name=node.name)
        else:
            ptr = self.builder.alloca(val.type, name=node.name)
        self.variables[node.name] = ptr
        self.builder.store(val, ptr)

    def visit_Assignment(self, node):
        if getattr(node, "target", None):
            ptr = self.get_ptr(node.target)
        else:
            if node.name not in self.variables:
                raise Exception(f"Undefined variable {node.name}")
            ptr = self.variables[node.name]
        val = self.visit(node.value)
        if ptr.type.pointee == self.f64 and val.type == self.i32:
            val = self.builder.sitofp(val, self.f64)
        self.builder.store(val, ptr)

    def visit_Variable(self, node):
        if node.name not in self.variables:
            raise Exception(f"Undefined variable {node.name}")
        return self.builder.load(self.variables[node.name])
    
    def visit_ExpressionStatement(self, node):
        return self.visit(node.expression)

    def visit_Import(self, node):
        pass

    # =====================================================
    # BINARY OPERATIONS
    # =====================================================
    def visit_BinaryOp(self, node):
        l = self.visit(node.left)
        r = self.visit(node.right)

        is_str = l.type == self.i8_ptr and r.type == self.i8_ptr

        if is_str and node.op == TokenType.PLUS:
            len1 = self.builder.call(self.strlen_func, [l])
            len2 = self.builder.call(self.strlen_func, [r])
            total = self.builder.add(len1, len2)
            buf = self.builder.call(self.malloc_func, [self.builder.add(total, self.i32(1))])
            self.builder.call(self.memcpy_func, [
                self.builder.bitcast(buf, self.i8_ptr),
                l, self.builder.zext(len1, self.i64), self.i1(0),
            ])
            off = self.builder.gep(buf, [len1])
            self.builder.call(self.memcpy_func, [
                self.builder.bitcast(off, self.i8_ptr),
                r, self.builder.zext(len2, self.i64), self.i1(0),
            ])
            null = self.builder.gep(buf, [total])
            self.builder.store(ir.Constant(ir.IntType(8), 0), null)
            return buf

        if is_str and node.op in (TokenType.EQUAL_EQUAL, TokenType.NOT_EQUAL):
            cmp = self.builder.call(self.strcmp_func, [l, r])
            eq = self.builder.icmp_signed("==", cmp, self.i32(0))
            if node.op == TokenType.NOT_EQUAL:
                eq = self.builder.not_(eq)
            return self.builder.zext(eq, self.i32)

        if l.type == self.i32 and r.type == self.f64:
            l = self.builder.sitofp(l, self.f64)
        elif l.type == self.f64 and r.type == self.i32:
            r = self.builder.sitofp(r, self.f64)

        is_float = isinstance(l.type, ir.DoubleType) or isinstance(r.type, ir.DoubleType)

        if node.op == TokenType.PLUS:
            return self.builder.fadd(l, r) if is_float else self.builder.add(l, r)

        if node.op == TokenType.MINUS:
            return self.builder.fsub(l, r) if is_float else self.builder.sub(l, r)

        if node.op == TokenType.MULTIPLY:
            return self.builder.fmul(l, r) if is_float else self.builder.mul(l, r)

        if node.op == TokenType.DIVIDE:
            return self.builder.fdiv(l, r) if is_float else self.builder.sdiv(l, r)

        if node.op in (TokenType.GREATER, TokenType.LESS, TokenType.EQUAL_EQUAL,
                       TokenType.NOT_EQUAL, TokenType.GREATER_EQUAL, TokenType.LESS_EQUAL):
            if is_float:
                op = {
                    TokenType.GREATER: ">",
                    TokenType.LESS: "<",
                    TokenType.EQUAL_EQUAL: "==",
                    TokenType.NOT_EQUAL: "!=",
                    TokenType.GREATER_EQUAL: ">=",
                    TokenType.LESS_EQUAL: "<=",
                }[node.op]
                cmp = self.builder.fcmp_ordered(op, l, r)
            else:
                op = {
                    TokenType.GREATER: ">",
                    TokenType.LESS: "<",
                    TokenType.EQUAL_EQUAL: "==",
                    TokenType.NOT_EQUAL: "!=",
                    TokenType.GREATER_EQUAL: ">=",
                    TokenType.LESS_EQUAL: "<=",
                }[node.op]
                cmp = self.builder.icmp_signed(op, l, r)

            return self.builder.zext(cmp, self.i32)

    # =====
    # PRINT
    # =========
    def visit_Print(self, node):
        val = self.visit(node.value)

        if val.type == self.i32:
            fmt = "%d\n\0"
        elif val.type == self.f64:
            fmt = "%f\n\0"
        else:
            fmt = "%s\n\0"

        fmt_ptr = self._fmt(fmt)
        self.builder.call(self.printf, [fmt_ptr, val])

    def _fmt(self, s):
        if s in self._fmt_cache:
            return self._fmt_cache[s]
        data = bytearray(s.encode())
        ty = ir.ArrayType(ir.IntType(8), len(data))
        name = f"fmt_{len(self._fmt_cache)}"
        glob = ir.GlobalVariable(self.module, ty, name=name)
        glob.global_constant = True
        glob.initializer = ir.Constant(ty, data)
        ptr = self.builder.gep(glob, [self.i32(0), self.i32(0)])
        self._fmt_cache[s] = ptr
        return ptr

    # ============
    # CONTROL FLOW
    # ==============
    def visit_If(self, node):
        cond = self.visit(node.condition)
        cond = self.builder.icmp_signed("!=", cond, self.i32(0))

        then_bb = self.builder.append_basic_block("then")
        else_bb = self.builder.append_basic_block("else") if node.else_body else None
        end_bb = self.builder.append_basic_block("end")

        self.builder.cbranch(cond, then_bb, else_bb or end_bb)

        self.builder.position_at_end(then_bb)
        for s in node.body:
            self.visit(s)
        if not self.builder.block.is_terminated:
            self.builder.branch(end_bb)

        if else_bb:
            self.builder.position_at_end(else_bb)
            for s in node.else_body:
                self.visit(s)
            if not self.builder.block.is_terminated:
                self.builder.branch(end_bb)

        self.builder.position_at_end(end_bb)

    def visit_While(self, node):
        cond_bb = self.builder.append_basic_block("cond")
        body_bb = self.builder.append_basic_block("body")
        end_bb = self.builder.append_basic_block("end")

        self.builder.branch(cond_bb)

        self.builder.position_at_end(cond_bb)
        cond = self.visit(node.condition)
        cond = self.builder.icmp_signed("!=", cond, self.i32(0))
        self.builder.cbranch(cond, body_bb, end_bb)

        self.builder.position_at_end(body_bb)
        for s in node.body:
            self.visit(s)
        self.builder.branch(cond_bb)

        self.builder.position_at_end(end_bb)

    # =============
    # FUNCTIONS 
    # =============
    def visit_Function(self, node):
        ret_ty = self.f64 if node.return_type == "float" else self.i32

        # dynamically determine parameter types
        param_types = []
        for p in node.params:
            if p["type"] == "float":
                param_types.append(self.f64)
            elif p["type"] in self.classes:
                
                param_types.append(self.classes[p["type"]]["type"].as_pointer())
            else:
                param_types.append(self.i32)

        fn_type = ir.FunctionType(ret_ty, param_types)
        func = ir.Function(self.module, fn_type, name=node.name)

        for i, p in enumerate(node.params):
            if param_types[i] == self.f64.as_pointer() or param_types[i] == self.i8_ptr:
                func.args[i].add_attribute("noalias")
                func.args[i].attributes.align = 8
            if p["name"] == "self":
                func.args[i].add_attribute("noalias")
                func.args[i].attributes.align = 8

        block = func.append_basic_block("entry")
        old_builder = self.builder
        old_vars = self.variables.copy()

        self.builder = ir.IRBuilder(block)
        self.variables = {}

        for i, p in enumerate(node.params):
            if p["name"] == "self":
                self.variables[p["name"]] = func.args[i]
            else:
                ptr = self.builder.alloca(param_types[i], name=p["name"])
                self.builder.store(func.args[i], ptr)
                self.variables[p["name"]] = ptr

        for stmt in node.body:
            self.visit(stmt)

        if not self.builder.block.is_terminated:
            self.builder.ret(ir.Constant(ret_ty, 0))

        self.builder = old_builder
        self.variables = old_vars

    def visit_Return(self, node):
        self.builder.ret(self.visit(node.value))


# =====================================================
    # CALLS (LEN & METHODS)
    # =====================================================
    def visit_Call(self, node):

        if getattr(node, "object", None) is not None:
            obj_ptr = self.variables[node.object.name]
            class_name = obj_ptr.type.pointee.name
            func_name = f"{class_name}_{node.name}"
            func = self.module.globals.get(func_name)
            args = [obj_ptr] + [self.visit(a) for a in node.args]
            return self.builder.call(func, args)

        # load_csv: call C FFI + track size for len()
        if node.name == "load_csv":
            filename = self.visit(node.args[0])
            num_values = self.visit(node.args[1])
            if node.args[1] and hasattr(node.args[1], 'value'):
                self._pending_csv_size = int(node.args[1].value)
            return self.builder.call(self.load_csv_func, [filename, num_values])

        # free(): bitcast pointer to i8* and call C free
        if node.name == "free":
            ptr_val = self.visit(node.args[0])
            if ptr_val.type != self.i8_ptr:
                ptr_val = self.builder.bitcast(ptr_val, self.i8_ptr)
            self.builder.call(self.free_func, [ptr_val])
            return ir.Constant(self.i32, 0)

        # Class constructor with heap allocation for large arrays (>4KB)
        if node.name in self.classes:
            class_info = self.classes[node.name]
            large_fields = class_info.get("large_fields", set())
            ptr = self.builder.alloca(class_info["type"], name=f"new_{node.name}")

            for i, default_node in enumerate(class_info["defaults"]):
                if not default_node:
                    continue
                field_ptr = self.builder.gep(ptr, [self.i32(0), self.i32(i)], inbounds=True)

                if i in large_fields:
                    val = self.visit(default_node)
                    elem_byte = 8 if isinstance(val.type.element, ir.DoubleType) else 4
                    total_bytes = val.type.count * elem_byte
                    raw = self.builder.call(self.malloc_func, [ir.Constant(self.i32, total_bytes)])
                    elem_ptr_ty = self.f64.as_pointer() if isinstance(val.type.element, ir.DoubleType) else self.i32.as_pointer()
                    typed = self.builder.bitcast(raw, elem_ptr_ty)
                    tmp = self.builder.alloca(val.type)
                    self.builder.store(val, tmp)
                    dst = self.builder.bitcast(typed, self.i8_ptr)
                    src = self.builder.bitcast(tmp, self.i8_ptr)
                    self.builder.call(self.memcpy_func, [
                        dst, src,
                        ir.Constant(self.i64, total_bytes),
                        ir.Constant(self.i1, 0),
                    ])
                    self.builder.store(typed, field_ptr)
                else:
                    val = self.visit(default_node)
                    if isinstance(val.type, ir.ArrayType) and isinstance(field_ptr.type.pointee, ir.PointerType):
                        temp_arr = self.builder.alloca(val.type)
                        self.builder.store(val, temp_arr)
                        val = self.builder.bitcast(temp_arr, field_ptr.type.pointee)
                    self.builder.store(val, field_ptr)

            return self.builder.load(ptr)

        # len(): check CSV size table first, then LLVM array types
        if node.name == "len":
            arg_node = node.args[0]
            if isinstance(arg_node, Variable) and arg_node.name in self.csv_var_sizes:
                return self.csv_var_sizes[arg_node.name]
            arg = self.visit(arg_node)
            if isinstance(arg.type, ir.ArrayType):
                length = arg.type.count
            elif hasattr(arg.type, "pointee") and isinstance(arg.type.pointee, ir.ArrayType):
                length = arg.type.pointee.count
            else:
                length = 0
            return ir.Constant(self.i32, length)

        if node.name in ["exp", "sqrt", "log"]:
            arg = self.visit(node.args[0])
            if arg.type != self.f64:
                arg = self.builder.sitofp(arg, self.f64)
            if node.name == "exp":
                return self.builder.call(self.exp_func, [arg])
            elif node.name == "sqrt":
                return self.builder.call(self.sqrt_func, [arg])
            elif node.name == "log":
                return self.builder.call(self.log_func, [arg])

        if node.name == "pow":
            base = self.visit(node.args[0])
            exp_val = self.visit(node.args[1])
            if base.type != self.f64:
                base = self.builder.sitofp(base, self.f64)
            if exp_val.type != self.f64:
                exp_val = self.builder.sitofp(exp_val, self.f64)
            return self.builder.call(self.pow_func, [base, exp_val])

        if node.name == "abs":
            arg = self.visit(node.args[0])
            if arg.type == self.f64:
                return self.builder.call(self.fabs_func, [arg])
            if arg.type == self.i32:
                neg = self.builder.icmp_signed("<", arg, self.i32(0))
                sub = self.builder.sub(self.i32(0), arg)
                return self.builder.select(neg, sub, arg)
            arg = self.builder.sitofp(arg, self.f64)
            return self.builder.call(self.fabs_func, [arg])

        if node.name == "round":
            arg = self.visit(node.args[0])
            if arg.type != self.f64:
                arg = self.builder.sitofp(arg, self.f64)
            return self.builder.call(self.round_func, [arg])

        if node.name == "get_time":
            return self.builder.call(self.get_time_func, [])

        func = self.module.globals.get(node.name)
        if func is None:
            raise Exception(f"Undefined function {node.name}")

        args = [self.visit(a) for a in node.args]
        return self.builder.call(func, args)
    
    
    # ==========
    # FOR LOOPS 
    # ==========
    
    def visit_For(self, node):
        limit_val = self.visit(node.iterable)
        start = ir.Constant(self.i32, 0)
        i_ptr = self.builder.alloca(self.i32, name=f"{node.var}_idx")
        self.builder.store(start, i_ptr)

        is_array = isinstance(limit_val.type, ir.ArrayType)
        if is_array:
            arr_len = limit_val.type.count
            limit = ir.Constant(self.i32, arr_len)
            arr_storage = self.builder.alloca(limit_val.type)
            self.builder.store(limit_val, arr_storage)
            elem_ptr = self.builder.alloca(limit_val.type.element, name=node.var)
            self.variables[node.var] = elem_ptr
        else:
            limit = limit_val
            self.variables[node.var] = i_ptr

        cond_bb = self.builder.append_basic_block("for.cond")
        body_bb = self.builder.append_basic_block("for.body")
        end_bb = self.builder.append_basic_block("for.end")

        self.builder.branch(cond_bb)
        self.builder.position_at_end(cond_bb)
        i = self.builder.load(i_ptr)
        cond = self.builder.icmp_signed("<", i, limit)
        self.builder.cbranch(cond, body_bb, end_bb)

        self.builder.position_at_end(body_bb)
        if is_array:
            i = self.builder.load(i_ptr)
            elem_gep = self.builder.gep(arr_storage, [self.i32(0), i], inbounds=True)
            elem_val = self.builder.load(elem_gep)
            self.builder.store(elem_val, elem_ptr)
        for s in node.body:
            self.visit(s)

        i = self.builder.load(i_ptr)
        self.builder.store(self.builder.add(i, self.i32(1)), i_ptr)
        self.builder.branch(cond_bb)
        self.builder.position_at_end(end_bb)

    # ============================
    # MULTI-DIMENSIONAL ARRAYS 
    # ===========================
    def get_ptr(self, node):
        """Recursively finds the exact memory address for variables, class fields, and chained array indices."""
        if type(node).__name__ == "Variable":
            return self.variables[node.name]
            
        elif type(node).__name__ == "MemberAccess":
            obj_ptr = self.variables[node.object.name]
            class_name = obj_ptr.type.pointee.name
            field_idx = self.classes[class_name]["indices"][node.member]
            return self.builder.gep(obj_ptr, [self.i32(0), self.i32(field_idx)], inbounds=True)
            
        elif type(node).__name__ == "ArrayIndex":
            base_ptr = self.get_ptr(node.array)
            idx = self.visit(node.index)
            
            
            if isinstance(base_ptr.type.pointee, ir.PointerType):
                actual_ptr = self.builder.load(base_ptr)
                return self.builder.gep(actual_ptr, [idx], inbounds=True)
            else:
                
                return self.builder.gep(base_ptr, [self.i32(0), idx], inbounds=True)
            
            
        raise Exception(f"Cannot get pointer for {type(node).__name__}")

    def visit_ArrayIndex(self, node):
        """Pulls a value out of an array at a specific index."""
       
        ptr = self.get_ptr(node)
        return self.builder.load(ptr) 


    def visit_ClassDecl(self, node):
        """Defines a new Object Struct in memory."""
        class_type = self.module.context.get_identified_type(node.name)
        
        field_types = []
        field_indices = {}
        field_defaults = [] 
        
        index = 0
        large_fields = set()
        for member in node.body:
            if type(member).__name__ == "VarDecl":
                if type(member.value).__name__ == "ArrayLiteral":
                    base = self.f64 if "float" in member.type_annotation else self.i32
                    dims = []
                    curr = member.value
                    while type(curr).__name__ == "ArrayLiteral":
                        dims.append(len(curr.elements))
                        curr = curr.elements[0] if len(curr.elements) > 0 else None
                    for d in reversed(dims):
                        base = ir.ArrayType(base, d)
                    ll_type = base
                    elem_byte = 8 if isinstance(base.element, ir.DoubleType) else 4
                    flat_count = 1
                    for d in dims:
                        flat_count *= d
                    if flat_count * elem_byte > 4096:
                        ll_type = base.element.as_pointer()
                        large_fields.add(index)
                elif member.type_annotation == "float":
                    ll_type = self.f64
                elif member.type_annotation == "int":
                    ll_type = self.i32
                elif member.type_annotation == "[float]":
                    ll_type = self.f64.as_pointer()
                else:
                    ll_type = self.i8_ptr

                field_types.append(ll_type)
                field_indices[member.name] = index
                field_defaults.append(member.value)
                index += 1
                
        class_type.set_body(*field_types)
        
        self.classes[node.name] = {
            "type": class_type,
            "indices": field_indices,
            "defaults": field_defaults,
            "large_fields": large_fields,
        }

        
        old_builder = self.builder
        
        
        for member in node.body:
            if type(member).__name__ == "Function":
                
                member.name = f"{node.name}_{member.name}"
                
                self.visit(member) 
                
        
        self.builder = old_builder
        

    def visit_MemberAccess(self, node):
        """Pulls a specific field out of an object (e.g. obj.field)."""
        
        obj_ptr = self.variables[node.object.name]
        
        
        class_name = obj_ptr.type.pointee.name
        
        
        field_idx = self.classes[class_name]["indices"][node.member]
        
        
        ptr = self.builder.gep(obj_ptr, [self.i32(0), self.i32(field_idx)], inbounds=True)
        return self.builder.load(ptr)

    
    # =====================================================
    # ARRAYS (DYNAMIC MEMORY)
    # =====================================================
    def visit_ArrayLiteral(self, node):
        elements = [self.visit(el) for el in node.elements]
        if not elements:
            return ir.Constant(ir.ArrayType(self.i32, 0), [])

        elem_ty = elements[0].type
        arr_ty = ir.ArrayType(elem_ty, len(elements))

        # --- THE LLVM MEMORY OPTIMIZATION  ---
        # If the array is purely raw numbers (like our massive CSV dataset)
        # we skip the 40,000 store instructions and package it instantly
        if all(isinstance(val, ir.Constant) for val in elements):
            return ir.Constant(arr_ty, elements)
        
        # Build array dynamically on the stack 
        tmp_ptr = self.builder.alloca(arr_ty, name="arr_literal_tmp")
        for i, val in enumerate(elements):
            idx = ir.Constant(self.i32, i)
            zero = ir.Constant(self.i32, 0)
            ptr = self.builder.gep(tmp_ptr, [zero, idx], inbounds=True)
            self.builder.store(val, ptr)
            
        return self.builder.load(tmp_ptr)
    
    def _enable_fast_math(self, ir_str):
        import re
        ir_str = re.sub(r'\b(fadd|fsub|fmul|fdiv|frem)\b', r'\1 fast', ir_str)
        ir_str = re.sub(r'(fcmp\s+)(o|u)?(eq|ne|lt|le|gt|ge|ord|uno)\b', r'\1fast \2\3', ir_str)
        return ir_str

    def execute(self):
        llvm_ir = str(self.module)
        llvm_ir = self._enable_fast_math(llvm_ir)
        mod = llvm.parse_assembly(llvm_ir)
        mod.verify()

        target_machine = llvm.Target.from_default_triple().create_target_machine()

        pto = llvm.create_pipeline_tuning_options(
            speed_level=3,
        )
        pb = llvm.create_pass_builder(target_machine, pto)
        pm = pb.getModulePassManager()
        pm.run(mod, pb)

        with llvm.create_mcjit_compiler(mod, target_machine) as ee:
            ee.finalize_object()
            func_ptr = ee.get_function_address("main")
            
           
            from ctypes import CFUNCTYPE, c_int
            import time  
            
            cfunc = CFUNCTYPE(c_int)(func_ptr)
            
            print("\n--- Running Program ---")
            
            start_time = time.time() 
            result = cfunc()
            end_time = time.time() 
            
            print(f"--- Program Exited with code {result} ---")
            print(f".cstar took: {end_time - start_time:.6f} seconds")
            return result

    def save_object(self, filename):
        llvm_ir = str(self.module)
        llvm_ir = self._enable_fast_math(llvm_ir)
        mod = llvm.parse_assembly(llvm_ir)
        mod.verify()

        pto = llvm.create_pipeline_tuning_options(speed_level=3)
        pb = llvm.create_pass_builder(
            llvm.Target.from_default_triple().create_target_machine(), pto
        )
        pm = pb.getModulePassManager()
        pm.run(mod, pb)

        target = llvm.Target.from_default_triple()
        target_machine = target.create_target_machine()
        obj_code = target_machine.emit_object(mod)

        with open(filename, "wb") as f:
            f.write(obj_code)
            
        print(f"Native Object File saved to: {filename}")