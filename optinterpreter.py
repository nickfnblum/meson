# Copyright 2013-2014 Jussi Pakkanen

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mparser
import coredata
import nodes
import os

forbidden_option_names = {'type': True,
                          'strip': True,
                          'coverage': True,
                          'pch': True,
                          'unity': True,
                          }

class OptionException(coredata.MesonException):
    pass

class UserOption:
    def __init__(self, kwargs):
        super().__init__()
        self.description = kwargs.get('description', '')

class UserStringOption(UserOption):
    def __init__(self, kwargs):
        super().__init__(kwargs)
        self.set_value(kwargs.get('value', ''))

    def set_value(self, newvalue):
        if not isinstance(newvalue, str):
            raise OptionException('Value of string option is not a string.')
        self.value = newvalue

class UserBooleanOption(UserOption):
    def __init__(self, kwargs):
        super().__init__(kwargs)
        self.set_value(kwargs.get('value', 'true'))

    def set_value(self, newvalue):
        if not isinstance(newvalue, bool):
            raise OptionException('Value of boolean option is not boolean.')
        self.value = newvalue

class UserComboOption(UserOption):
    def __init__(self, kwargs):
        super().__init__(kwargs)
        if 'choices' not in kwargs:
            raise OptionException('Combo option missing "choices" keyword.')
        self.choices = kwargs['choices']
        if not isinstance(self.choices, list):
            raise OptionException('Combo choices must be an array.')
        for i in self.choices:
            if not isinstance(i, str):
                raise OptionException('Combo choice elements must be strings.')
        self.value = kwargs.get('value', self.choices[0])

    def set_value(self, newvalue):
        if newvalue not in self.choices:
            raise OptionException('Combo value must be one of the choices.')
        self.value = newvalue

option_types = {'string' : UserStringOption,
                'boolean' : UserBooleanOption,
                'combo' : UserComboOption,
                }

class OptionInterpreter:
    def __init__(self, subproject):
        self.options = {}
        self.subproject = subproject
    
    def process(self, option_file):
        try:
            ast = mparser.build_ast(open(option_file, 'r').read())
        except coredata.MesonException as me:
            me.file = option_file
            raise me
        if not isinstance(ast, nodes.CodeBlock):
            e = OptionException('Option file is malformed.')
            e.lineno = ast.lineno()
            raise e
        statements = ast.get_statements()
        for cur in statements:
            try:
                self.evaluate_statement(cur)
            except Exception as e:
                e.lineno = cur.lineno()
                e.file = os.path.join('meson_options.txt')
                raise e

    def reduce_single(self, arg):
        if isinstance(arg, nodes.AtomExpression) or isinstance(arg, nodes.AtomStatement):
            return self.get_variable(arg.value)
        elif isinstance(arg, str):
            return arg
        elif isinstance(arg, nodes.StringExpression) or isinstance(arg, nodes.StringStatement):
            return arg.get_value()
        elif isinstance(arg, nodes.BoolStatement) or isinstance(arg, nodes.BoolExpression):
            return arg.get_value()
        elif isinstance(arg, nodes.ArrayStatement):
            return [self.reduce_single(curarg) for curarg in arg.args.arguments]
        elif isinstance(arg, nodes.IntStatement):
            return arg.get_value()
        else:
            raise OptionException('Arguments may only be string, int, bool, or array of those.')

    def reduce_arguments(self, args):
        assert(isinstance(args, nodes.Arguments))
        if args.incorrect_order():
            raise OptionException('All keyword arguments must be after positional arguments.')
        reduced_pos = [self.reduce_single(arg) for arg in args.arguments]
        reduced_kw = {}
        for key in args.kwargs.keys():
            if not isinstance(key, str):
                raise OptionException('Keyword argument name is not a string.')
            a = args.kwargs[key]
            reduced_kw[key] = self.reduce_single(a)
        return (reduced_pos, reduced_kw)

    def evaluate_statement(self, node):
        if not isinstance(node, nodes.FunctionCall):
            raise OptionException('Option file may only contain option definitions')
        func_name = node.get_function_name()
        if func_name != 'option':
            raise OptionException('Only calls to option() are allowed in option files.')
        (posargs, kwargs) = self.reduce_arguments(node.arguments)
        if 'type' not in kwargs:
            raise OptionException('Option call missing mandatory "type" keyword argument')
        opt_type = kwargs['type']
        if not opt_type in option_types:
            raise OptionException('Unknown type %s.' % opt_type)
        if len(posargs) != 1:
            raise OptionException('Option() must have one (and only one) positional argument')
        opt_name = posargs[0]
        if not isinstance(opt_name, str):
            raise OptionException('Positional argument must be a string.')
        if opt_name in forbidden_option_names:
            raise OptionException('Option name %s is reserved.' % opt_name)
        if self.subproject != '':
            opt_name = self.subproject + '-' + opt_name
        opt = option_types[opt_type](kwargs)
        if opt.description == '':
            opt.description = opt_name
        self.options[opt_name] = opt
