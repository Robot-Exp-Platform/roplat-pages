---
output: word_document
---

# 平台建模思路

## 问题描述

在二维空间中有$n(n>2)$个长非均匀刚体,首尾使用铰链相连,每一处铰链位置提供扭矩使得两个相连杆产生相对旋转,第一个刚体的首端链接在一个固定的旋转电机上,在力矩、系统初始条件、杆参数等已知情况下求解整个系统的运动.

## 问题求解

+ 假设将刚体抽象为不均匀杆,一共有$n$个,每个杆的质量分布$\rho _i$与长度$l_i$均已知,可求参数为**质量,质心位置,转动惯量,逆转动惯量**$m_i,\lambda _i,I_i,I_i'$,其中$i=0,1,2,\cdots,n$,其中初始位置速度条件以及每个关节处的力矩大小均为已知。*(假设杆可以被抽象为一根质量不均匀的二维线段,即质心只有可能出现在线段内,且以更靠近首端的位置为计算起点)*
  + 参数求解方法：$$m_i=\int dm,\lambda _i= \frac{1}{l_i}\int xdm,I_i=\int x^2dm,I_i'=\int (l_i-x)^2dm$$
+ 取每个关节（包括第一杆首端的固定关节与最后一杆的悬空关节）的加速度为$\vec{a_i}$，取每个关节的力矩为$M^i$（指$i$杆对$i+1$杆的作用力矩）,取每个关节的力为$\vec{N^i}$（指$i$杆对$i+1$杆的作用力）,则可以列出每个关节的动量方程和角动量方程.

+ 角动量方程
  + $$I_i\frac{\vec{l_i}\times (\vec{a_i}-\vec{a_{i-1}})}{l_i^2}+m_i\lambda _i\vec{l_i}\times \vec{a_{i-1}}=M^{i-1}-M^i-\vec{l_i}\times \vec{N^i} $$
+ 动量方程
  + $$m(\lambda ^i\vec{a_i}+(1-\lambda ^i)\vec{a_{i-1}})=-\vec{N^i}+\vec{N^{i-1}} $$
+ 约束方程
  + $$ l_i^2=(\vec{x_i}-\vec{x_{i-1}})(\bar{\vec{x_i}}-\bar{\vec{x_{i-1}}})$$
  + 即$$ (\vec{v_i}-\vec{v_{i-1}})\cdot (\vec{x_i}-\vec{x_{i-1}})=0$$
  + 求导有
  + $$(x_i - x_{i-1})^T(a_i - a_{i-1}) = -(v_i - v_{i-1})^2$$
+ 针对$n$个杆可以列出$4n$个方程,每一个关节点与末端提供$4$个变量,其中 $a_0=0,N_n$已知,剩余 $4(n+1)-4=4n$个变量,联立可以求解方程。
+ 通过方程联立求解得到每一时刻的每一个关节的加速度后，通过积分可以得到每一时刻的每一个关节的速度和位移。
  + $$\vec{v_{it}}=\int_0^t \vec{a_i} dt +\vec{v_{i0}}\qquad \vec{x_{it}}=\int_0^t \vec{v_{it}} dt +\vec{x_{i0}}$$

## 方程整理

+ 约定$l=\begin{bmatrix}x\\y \end{bmatrix}$, $\tilde{l}=\begin{bmatrix} -y&x \end{bmatrix}$,并取$E=\begin{bmatrix} 1&0 \\ 0&1 \end{bmatrix}$,认为$0$指代可以填充该位置的$0$矩阵.
$$\frac{I_i}{l_i^2}\tilde{l_i}(\vec{a_i}-\vec{a_{i-1}})+\tilde{l_i}\vec{N^i}+m_i \lambda _i\tilde{l_i}\vec{a_{i-1}}=M^{i-1}-M^i$$
$$m\lambda ^i\vec{a_i}+m(1-\lambda ^i)\vec{a_{i-1}}+\vec{N^i}-\vec{N^{i-1}}=0 $$
$$(\vec{x_i}-\vec{x_{i-1}})^T\vec{a_i}-(\vec{x_i}-\vec{x_{i-1}})^T\vec{a_{i-1}}=-(\vec{v_i}-\vec{v_{i-1}})^2$$

$$\begin{bmatrix}
    \frac{I_i}{l_i^2}\tilde{l_i} & (m_i \lambda _i-\frac{I_i}{l_i^2})\tilde{l_i} & \tilde{l_i} & 0 \\
    m_i\lambda ^iE & m_i(1-\lambda ^i)E & E & -E \\
    (\vec{x_i}-\vec{x_{i-1}})^T & -(\vec{x_i}-\vec{x_{i-1}})^T & 0 & 0
    \end{bmatrix}
    \begin{bmatrix}
    \vec{a_i} \\ \vec{a_{i-1}} \\ \vec{N^i} \\ \vec{N^{i-1}}
    \end{bmatrix} = \begin{bmatrix}
    -1&1\\0&0\\0&0
    \end{bmatrix}
    \begin{bmatrix}
    M^i \\ M^{i-1}
    \end{bmatrix} + \begin{bmatrix}
    0 \\ 0 \\ -(\vec{v_i}-\vec{v_{i-1}})^2
    \end{bmatrix}$$
## 矩阵整理

针对$n$个杆写出大矩阵有
$$\Gamma\begin{bmatrix}
  \mathcal{A} \\ \mathcal{N}
\end{bmatrix} = \begin{bmatrix}
  \Gamma ^1_{n\times 2n} & \Gamma ^2_{n\times 2n} \\
  \Gamma ^3_{2n\times 2n} & \Gamma ^4_{2n\times 2n} \\
    \Gamma ^5_{n\times 2n} & \Gamma ^6_{n\times 2n} \\
  \end{bmatrix}
  \begin{bmatrix}
  \mathcal{A}_{2n\times 1} \\ \mathcal{N}_{2n\times 1}
\end{bmatrix}
=\begin{bmatrix}
  J \\ 0
\end{bmatrix}\mathcal{M}-C$$
其中
$$\Gamma ^1_{n\times 2n}=\begin{bmatrix}
\frac{I_n}{l_n^2}\tilde{l_n} & (m_n \lambda _n-\frac{I_n}{l_n^2})\tilde{l_n} & 0 & \cdots & 0 \\
0 & \frac{I_{n-1}}{l_{n-1}^2}\tilde{l_{n-1}} & (m_{n-1} \lambda _{n-1}-\frac{I_{n-1}}{l_{n-1}^2})\tilde{l_{n-1}} & \cdots & 0 \\
\vdots &  &  & \ddots & \vdots \\
0  & \cdots & 0 & 0 & \frac{I_1}{l_1^2}\tilde{l_1}
\end{bmatrix};
\Gamma ^2_{n\times 2n}=\begin{bmatrix}
 0 & 0 & \cdots & 0 \\
\tilde{l_{n-1}} & 0 & \cdots & 0 \\
\vdots & \ddots & & \vdots \\
0  & \cdots &  \tilde{l_1} & 0 \\
\end{bmatrix}$$
$$ \Gamma ^3_{2n\times 2n}=\begin{bmatrix}
  m_n\lambda _nE & m_n(1-\lambda_n)E & 0 & 0 & \cdots & 0  \\
  0 & m_{n-1}\lambda _{n-1}E & m_{n-1}(1-\lambda_{n-1})E & 0 & \cdots & 0 \\
  \vdots  &  &  & \ddots &  & \vdots \\
  0 & \cdots & 0 & 0 & m_2\lambda _2E & m_2(1-\lambda_2)E \\
  0 & \cdots & 0 & 0 & 0 & m_1\lambda _1E  \\
\end{bmatrix};
 \Gamma ^4_{2n\times 2n}=\begin{bmatrix}
  -E & 0 & 0 & \cdots & 0  \\
  E & -E & 0 & \cdots & 0 \\
  \vdots  &  & \ddots &  & \vdots \\
  0 & \cdots & 0 & E & -E \\
\end{bmatrix}$$
$$\Gamma ^5_{n\times 2n}=\begin{bmatrix}
  (\vec{x_n}-\vec{x_{n-1}})^T & -(\vec{x_n}-\vec{x_{n-1}})^T & 0 & \cdots & 0 \\
  0 & (\vec{x_{n-1}}-\vec{x_{n-2}})^T & -(\vec{x_{n-1}}-\vec{x_{n-2}})^T & \cdots & 0 \\
  \vdots &  & \ddots &  & \vdots \\
  0 & \cdots & 0 & 0 & (\vec{x_1}-\vec{x_0})^T
\end{bmatrix}; \Gamma ^6_{n\times 2n}=0$$
$$J_{n\times n}=\begin{bmatrix}
1&0&\cdots &0 \\
-1&1&\cdots &0 \\
\vdots & &\ddots &\vdots \\
0&\cdots &-1&1
\end{bmatrix}C_{4n\times 1}=\begin{bmatrix}
0 \\ 0 \\ (\vec{v_n}-\vec{v_{n-1}})^2 \\ \vdots \\ (\vec{v_1}-\vec{v_0})^2
\end{bmatrix}$$
$$M_{n\times 1}=\begin{bmatrix}
M^{n-1} \\ \vdots \\ M^1\\ M^0
\end{bmatrix},\mathcal{A}_{2n\times 1}=\begin{bmatrix}
\vec{a_n} \\ \vec{a_{n-1}} \\ \vdots \\ \vec{a_1}
\end{bmatrix},\mathcal{N}_{2n\times 1}=\begin{bmatrix}
\vec{N^{n-1}} \\ \vdots \\ \vec{N^1} \\ \vec{N^0}
\end{bmatrix}$$
当n=1时，方程有
$$\begin{bmatrix}
\frac{I_1}{l_1^2}\tilde{l_1}  & 0 \\
m_1\lambda ^1E & -E \\
\vec{x_1}^T & 0
\end{bmatrix}
\begin{bmatrix}
\vec{a_1} \\ \vec{N^0}
\end{bmatrix} = \begin{bmatrix}
-1\\0\\0
\end{bmatrix}M^1 + \begin{bmatrix}
0 \\ 0 \\ -(\vec{v_1})^2
\end{bmatrix}$$

### 整体流程
![alt text](image.png)
