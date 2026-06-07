import ast
import math
import operator

from discord.ext import commands


CALC_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

CALC_FUNCTIONS = {
    "sqrt": math.sqrt,
}

MAX_CALC_POWER = 100
MAX_CALC_ABS_RESULT = 10**100


def calculate_expression(expression: str):
    expression = expression.replace("^", "**")
    tree = ast.parse(expression, mode="eval")

    def eval_node(node):
        if isinstance(node, ast.Expression):
            return eval_node(node.body)

        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value

        if isinstance(node, ast.BinOp) and type(node.op) in CALC_OPERATORS:
            left = eval_node(node.left)
            right = eval_node(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > MAX_CALC_POWER:
                raise ValueError("Số mũ quá lớn.")

            result = CALC_OPERATORS[type(node.op)](left, right)
            if abs(result) > MAX_CALC_ABS_RESULT:
                raise ValueError("Kết quả quá lớn.")
            return result

        if isinstance(node, ast.UnaryOp) and type(node.op) in CALC_OPERATORS:
            return CALC_OPERATORS[type(node.op)](eval_node(node.operand))

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in CALC_FUNCTIONS
            and len(node.args) == 1
            and not node.keywords
        ):
            return CALC_FUNCTIONS[node.func.id](eval_node(node.args[0]))

        raise ValueError("Biểu thức không hợp lệ.")

    return eval_node(tree)


class CalcCommand:
    @commands.command()
    async def calc(self, ctx, *, expression: str):
        try:
            result = calculate_expression(expression)
        except ZeroDivisionError:
            await ctx.reply("Không thể chia cho 0.", mention_author=False)
            return
        except (SyntaxError, ValueError, TypeError, OverflowError):
            await ctx.reply(
                "Biểu thức không hợp lệ. Ví dụ: `tcalc (2 + 3) * 4`",
                mention_author=False,
            )
            return

        await ctx.reply(f"Kết quả: {result}", mention_author=False)
